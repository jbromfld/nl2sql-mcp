"""
Refactored Slot Filler for NL2SQL

Key improvements:
- Schema-agnostic core extraction (fast, testable, no dependencies)
- Preserves original time units (no lossy conversion)
- Unified normalization in one place
- Clear separation: extract → normalize → validate
- Extensible pattern system
"""

import re
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum


class TimeUnit(Enum):
    """Time unit enumeration"""
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


@dataclass
class TimeRange:
    """Structured time range representation"""
    value: int
    unit: TimeUnit
    raw_text: str

    def to_sql_filter(self, date_column: str = "date") -> str:
        """Convert to SQL date filter"""
        now = datetime.now()

        if self.unit == TimeUnit.DAYS:
            start_date = now - timedelta(days=self.value)
        elif self.unit == TimeUnit.WEEKS:
            start_date = now - timedelta(weeks=self.value)
        elif self.unit == TimeUnit.MONTHS:
            # Approximate: 30 days per month
            start_date = now - timedelta(days=self.value * 30)
        elif self.unit == TimeUnit.YEARS:
            start_date = now - timedelta(days=self.value * 365)
        else:
            start_date = now

        return f"{date_column} >= '{start_date.date()}'"

    def to_months_approx(self) -> int:
        """Convert to months (for backward compatibility)"""
        if self.unit == TimeUnit.MONTHS:
            return self.value
        elif self.unit == TimeUnit.WEEKS:
            return max(1, self.value // 4)
        elif self.unit == TimeUnit.DAYS:
            return max(1, self.value // 30)
        elif self.unit == TimeUnit.YEARS:
            return self.value * 12
        return 1


@dataclass
class ExtractedSlots:
    """Structured representation of extracted slots"""
    # Core slots
    app_name: Optional[str] = None
    environment: Optional[str] = None
    time_range: Optional[TimeRange] = None
    specific_date: Optional[str] = None
    version: Optional[str] = None
    branch: Optional[str] = None
    limit: Optional[int] = None

    # Metadata
    raw_query: str = ""
    table_hint: Optional[str] = None
    operation_type: Optional[str] = None
    confidence: str = "high"

    # Warnings/issues
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding None values)"""
        result = {}
        for key in self.__dataclass_fields__:
            value = getattr(self, key)
            if value is not None:
                if isinstance(value, TimeRange):
                    result[key] = {
                        "value": value.value,
                        "unit": value.unit.value,
                        "raw_text": value.raw_text
                    }
                elif isinstance(value, list) and not value:
                    continue  # Skip empty lists
                else:
                    result[key] = value
        return result

    def to_cache_key(self) -> str:
        """Generate cache key from normalized slots"""
        parts = [
            self.operation_type or "SELECT",
            self.table_hint or "unknown",
            self.app_name or "*",
            self.environment or "*",
            f"{self.time_range.unit.value}:{self.time_range.value}" if self.time_range else "*",
            str(self.limit) if self.limit else "*"
        ]
        return ":".join(parts)


class SlotExtractor:
    """Core slot extraction using pure pattern matching"""

    # Environment patterns with normalization
    ENV_PATTERNS = [
        (r'\b(prod|production)\b', 'PROD'),
        (r'\b(stag(?:ing)?)\b', 'STAGING'),
        (r'\b(dev|development)\b', 'DEV'),
        (r'\b(qa|test)\b', 'QA'),
    ]

    # Time range patterns (preserves original units)
    TIME_PATTERNS = [
        # With explicit numbers
        r'(?:last|past|previous|in the last|in the past)\s+(\d+)\s+(day|week|month|year)s?',
        r'(\d+)\s+(day|week|month|year)s?\s+ago',
        # Without numbers (implies 1 unit)
        r'(?:in the last|in the past|over the last|over the past)\s+(week|month|year)',
    ]

    # Relative time keywords
    RELATIVE_TIME = {
        r'\b(today)\b': ('today', None),
        r'\b(yesterday)\b': ('yesterday', None),
        r'\bthis\s+week\b': ('this_week', None),
        r'\blast\s+week\b': ('last_week', None),
        r'\bthis\s+month\b': ('this_month', None),
        r'\blast\s+month\b': ('last_month', None),
    }

    # App name patterns (ordered by specificity)
    APP_PATTERNS = [
        # Explicit "app" keyword patterns (highest priority)
        r'(?:for|of|about)\s+app(?:lication)?\s+["\']?([a-zA-Z][\w\-/]+)["\']?',
        r'app(?:lication)?\s+["\']?([a-zA-Z][\w\-/]+)["\']?',

        # App name before time expressions (high priority)
        r'(?:for|of|about)\s+([a-zA-Z][\w\-/]+)\s+(?:app\s+)?(?:in\s+the\s+(?:last|past)|over\s+the)',

        # Quoted app names (high priority)
        r'["\']([a-zA-Z][\w\-/]+)["\']',

        # App name in deployment/test context (medium priority)
        # Only match if preceded by preposition to avoid catching verbs
        r'(?:for|of)\s+([a-zA-Z][\w\-/]+)\s+(?:deployment|test|release|build)s?',

        # Generic prepositional patterns (lowest priority)
        r'(?:for|of|about)\s+([a-zA-Z][\w\-/]+)(?:\s+(?:to|in|on))?',
    ]

    # Limit patterns
    LIMIT_PATTERNS = [
        r'(?:last|latest|most recent)\s+(\d+)\s+(?:deployment|test|result|record)s?',
        r'(?:show|get|give)\s+(?:me\s+)?(?:the\s+)?(\d+)',
        r'(?:top|first)\s+(\d+)',
        r'limit\s+(?:to\s+)?(\d+)',
        r'(\d+)\s+(?:result|record)s?',
    ]

    # Table hints (order matters - check test patterns first as they're more specific)
    TABLE_HINTS = [
        (r'\b(tests?|testing|test\s+results?)\b', 'test_data'),
        (r'\b(deployments?|deploy|release|rollback)\b', 'deployment_data'),
    ]

    # Operation types
    OPERATION_PATTERNS = [
        (r'\b(how many|count|total|number)\b', 'COUNT'),
        (r'\b(list|show|get|what|find|display)\b', 'SELECT'),
        (r'\b(latest|last|most recent)\b', 'SELECT_LATEST'),
    ]

    def __init__(self, known_apps: Optional[List[str]] = None):
        """
        Args:
            known_apps: Optional list of known app names for validation
        """
        self.known_apps = [app.lower() for app in (known_apps or [])]
        self._time_word_blocklist = {
            'the', 'last', 'past', 'previous', 'next', 'this', 'that',
            'in', 'for', 'of', 'to', 'about', 'day', 'week', 'month', 'year'
        }
        # Block common SQL/query operation words
        self._operation_word_blocklist = {
            'list', 'show', 'get', 'find', 'display', 'count', 'select',
            'what', 'how', 'many', 'give', 'me', 'the'
        }

    def extract(self, query: str) -> ExtractedSlots:
        """Extract all slots from query"""
        slots = ExtractedSlots(raw_query=query)
        query_lower = query.lower()

        # Extract in order of independence (least dependent first)
        slots.environment = self._extract_environment(query_lower)
        slots.time_range = self._extract_time_range(query_lower)
        slots.specific_date = self._extract_specific_date(query_lower)
        slots.version = self._extract_version(query)
        slots.branch = self._extract_branch(query)
        slots.limit = self._extract_limit(query_lower)
        slots.table_hint = self._extract_table_hint(query_lower)
        slots.operation_type = self._extract_operation(query_lower)

        # Extract app name last (most context-dependent)
        slots.app_name = self._extract_app_name(query, query_lower, slots)

        # Calculate confidence
        slots.confidence = self._calculate_confidence(slots)

        return slots

    def _extract_environment(self, query: str) -> Optional[str]:
        """Extract and normalize environment"""
        for pattern, normalized in self.ENV_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return normalized
        return None

    def _extract_time_range(self, query: str) -> Optional[TimeRange]:
        """Extract time range preserving original units"""
        # Try explicit time patterns first (highest priority)
        for pattern in self.TIME_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Check if we have a number or just a unit
                groups = match.groups()

                if len(groups) == 2 and groups[0].isdigit():
                    # Pattern with number: "last 3 weeks"
                    value = int(groups[0])
                    unit_str = groups[1].lower()
                elif len(groups) == 2 and not groups[0].isdigit():
                    # Pattern without number: "in the last week" (implies 1)
                    value = 1
                    unit_str = groups[0].lower()
                elif len(groups) == 1:
                    # Pattern with only unit: "in the last week"
                    value = 1
                    unit_str = groups[0].lower()
                else:
                    continue

                # Map to enum
                unit_map = {
                    'day': TimeUnit.DAYS,
                    'week': TimeUnit.WEEKS,
                    'month': TimeUnit.MONTHS,
                    'year': TimeUnit.YEARS,
                }
                unit = unit_map.get(unit_str)

                if unit:
                    return TimeRange(
                        value=value,
                        unit=unit,
                        raw_text=match.group(0)
                    )

        # Try relative time keywords only if explicit patterns didn't match
        for pattern, (ref_name, _) in self.RELATIVE_TIME.items():
            if re.search(pattern, query, re.IGNORECASE):
                # Convert to TimeRange equivalents
                conversions = {
                    'today': (0, TimeUnit.DAYS),
                    'yesterday': (1, TimeUnit.DAYS),
                    'this_week': (7, TimeUnit.DAYS),
                    # Previous calendar week ≈ 7 days
                    'last_week': (7, TimeUnit.DAYS),
                    'this_month': (30, TimeUnit.DAYS),
                    'last_month': (30, TimeUnit.DAYS),
                }
                if ref_name in conversions:
                    value, unit = conversions[ref_name]
                    return TimeRange(value=value, unit=unit, raw_text=ref_name)

        return None

    def _extract_specific_date(self, query: str) -> Optional[str]:
        """Extract specific dates (YYYY-MM-DD format)"""
        # ISO format
        match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', query)
        if match:
            date_str = match.group(1)
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except ValueError:
                pass

        # US format MM/DD/YYYY
        match = re.search(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', query)
        if match:
            try:
                parsed = datetime.strptime(match.group(1), '%m/%d/%Y')
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                pass

        return None

    def _extract_app_name(self, query: str, query_lower: str, slots: ExtractedSlots) -> Optional[str]:
        """Extract app name with context awareness"""
        # Check known apps first (exact match)
        for app in self.known_apps:
            # Use word boundaries to avoid partial matches
            if re.search(rf'\b{re.escape(app)}\b', query_lower):
                # Return with original casing from query
                match = re.search(
                    rf'\b({re.escape(app)})\b', query, re.IGNORECASE)
                if match:
                    return match.group(1)

        # Try patterns in order of specificity
        for pattern in self.APP_PATTERNS:
            matches = list(re.finditer(pattern, query, re.IGNORECASE))

            for match in matches:
                candidate = match.group(1).strip()

                # Skip if in blocklist
                if candidate.lower() in self._time_word_blocklist:
                    continue

                # Skip if it's actually an environment
                if candidate.upper() in ['PROD', 'STAGING', 'DEV', 'QA']:
                    continue

                # Skip if followed by time unit (likely not an app)
                remaining = query[match.end():].lower()
                if re.match(r'^\s+(day|week|month|year)s?\b', remaining):
                    continue

                # Skip if it appears in a time expression context
                preceding = query[max(0, match.start()-20)                                  :match.start()].lower()
                if any(phrase in preceding for phrase in ['in the last', 'in the past', 'over the']):
                    # Make sure candidate appears BEFORE the time phrase
                    if 'last' in query_lower[match.start():]:
                        continue

                return candidate

        return None

    def _extract_version(self, query: str) -> Optional[str]:
        """Extract version string"""
        patterns = [
            r'version\s+["\']?([\d\.]+)["\']?',
            r'\bv([\d\.]+)\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_branch(self, query: str) -> Optional[str]:
        """Extract branch name"""
        patterns = [
            r'branch\s+["\']?([\w\-/]+)["\']?',
            r'on\s+["\']?([\w\-/]+)["\']?\s+branch',
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_limit(self, query: str) -> Optional[int]:
        """Extract result limit"""
        for pattern in self.LIMIT_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def _extract_table_hint(self, query: str) -> Optional[str]:
        """Determine likely table based on keywords"""
        for pattern, table in self.TABLE_HINTS:
            if re.search(pattern, query, re.IGNORECASE):
                return table

        # Default to deployment_data if ambiguous
        return 'deployment_data'

    def _extract_operation(self, query: str) -> Optional[str]:
        """Determine SQL operation type"""
        for pattern, op_type in self.OPERATION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return op_type

        return 'SELECT'

    def _calculate_confidence(self, slots: ExtractedSlots) -> str:
        """Calculate extraction confidence"""
        filled_slots = sum([
            slots.app_name is not None,
            slots.environment is not None,
            slots.time_range is not None or slots.specific_date is not None,
        ])

        if filled_slots >= 3:
            return "high"
        elif filled_slots >= 2:
            return "medium"
        else:
            return "low"


class SlotValidator:
    """Optional schema-aware validation (separate from extraction)"""

    def __init__(self, valid_apps: Optional[List[str]] = None,
                 valid_envs: Optional[List[str]] = None):
        """
        Args:
            valid_apps: List of valid app names from DB
            valid_envs: List of valid environments from DB
        """
        self.valid_apps = [app.lower() for app in (valid_apps or [])]
        self.valid_envs = [env.upper() for env in (valid_envs or [])]

    def validate(self, slots: ExtractedSlots) -> Dict[str, Any]:
        """Validate slots against known valid values"""
        validation = {
            "is_valid": True,
            "warnings": [],
            "suggestions": []
        }

        # Validate app name
        if slots.app_name and self.valid_apps:
            if slots.app_name.lower() not in self.valid_apps:
                validation["warnings"].append(
                    f"App '{slots.app_name}' not found in database"
                )
                validation["suggestions"].append(
                    f"Valid apps: {', '.join(self.valid_apps[:5])}"
                )

        # Validate environment
        if slots.environment and self.valid_envs:
            if slots.environment.upper() not in self.valid_envs:
                validation["warnings"].append(
                    f"Environment '{slots.environment}' not found in database"
                )
                validation["suggestions"].append(
                    f"Valid environments: {', '.join(self.valid_envs)}"
                )

        # Check for minimal query requirements
        if not any([slots.app_name, slots.environment, slots.time_range, slots.specific_date]):
            validation["is_valid"] = False
            validation["warnings"].append(
                "Query too vague - please specify app, environment, or time range"
            )

        return validation


# Convenience functions
def extract_slots(query: str, known_apps: Optional[List[str]] = None) -> ExtractedSlots:
    """Extract slots from natural language query"""
    extractor = SlotExtractor(known_apps=known_apps)
    return extractor.extract(query)


def validate_slots(slots: ExtractedSlots,
                   valid_apps: Optional[List[str]] = None,
                   valid_envs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Validate extracted slots"""
    validator = SlotValidator(valid_apps=valid_apps, valid_envs=valid_envs)
    return validator.validate(slots)


# Example usage and tests
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Slot Filler for NL2SQL')
    parser.add_argument('--test', action='store_true',
                        help='Run test extractions')
    args = parser.parse_args()

    if args.test:
        # Test queries
        test_queries = [
            "What's the last deployed version to prod of user-service",
            "Show me deployments for frontend in the last week",
            "How many tests ran for api-gateway this week",
            "Get the latest 5 deployments for auth-service in dev",
            "What about backend app deployments in the last 30 days?",
            "Show 10 deployments to staging",
            "frontend/api deployments over the last 3 months",
            "Give me test results for user-service from yesterday",
            "List deployments on 2024-01-15",
        ]

        # Initialize with known apps
        known_apps = ['user-service', 'api-gateway',
                      'auth-service', 'frontend', 'backend']

        print("=" * 80)
        print("SLOT EXTRACTION RESULTS")
        print("=" * 80)

        for query in test_queries:
            slots = extract_slots(query, known_apps=known_apps)
            validation = validate_slots(slots, valid_apps=known_apps,
                                        valid_envs=['PROD', 'STAGING', 'DEV', 'QA'])

            print(f"\nQuery: {query}")
            print(f"  App: {slots.app_name}")
            print(f"  Env: {slots.environment}")
            if slots.time_range:
                print(
                    f"  Time: {slots.time_range.value} {slots.time_range.unit.value}")
                print(f"    → SQL: {slots.time_range.to_sql_filter()}")
            print(f"  Date: {slots.specific_date}")
            print(f"  Limit: {slots.limit}")
            print(f"  Table: {slots.table_hint}")
            print(f"  Operation: {slots.operation_type}")
            print(f"  Confidence: {slots.confidence}")
            print(f"  Cache Key: {slots.to_cache_key()}")

            if validation["warnings"]:
                print(f"  ⚠ Warnings: {', '.join(validation['warnings'])}")
    else:
        print("Slot Filler module loaded. Use --test flag to run test extractions.")
