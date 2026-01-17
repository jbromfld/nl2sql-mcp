-- ============================================================================
-- CI/CD Database Schema with Sample Data
-- ============================================================================

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS test_data CASCADE;
DROP TABLE IF EXISTS deployment_data CASCADE;
DROP TABLE IF EXISTS nl2sql_cache CASCADE;

-- ============================================================================
-- DEPLOYMENT DATA TABLE
-- ============================================================================
CREATE TABLE deployment_data (
    id SERIAL PRIMARY KEY,
    app_name VARCHAR(100) NOT NULL,
    app_version VARCHAR(50) NOT NULL,
    build_url VARCHAR(500),
    app_repo VARCHAR(200),
    deploy_env VARCHAR(20) NOT NULL,
    rollback_version VARCHAR(50),
    deploy_result VARCHAR(20) NOT NULL,
    deploy_duration_seconds INTEGER,
    deployed_by VARCHAR(100),
    date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for common queries
    CONSTRAINT deployment_result_check CHECK (deploy_result IN ('SUCCESS', 'FAILURE', 'ABORTED', 'UNSTABLE'))
);

CREATE INDEX idx_deployment_app_name ON deployment_data(app_name);
CREATE INDEX idx_deployment_env ON deployment_data(deploy_env);
CREATE INDEX idx_deployment_date ON deployment_data(date DESC);
CREATE INDEX idx_deployment_result ON deployment_data(deploy_result);
CREATE INDEX idx_deployment_app_env_date ON deployment_data(app_name, deploy_env, date DESC);

-- ============================================================================
-- TEST DATA TABLE
-- ============================================================================
CREATE TABLE test_data (
    id SERIAL PRIMARY KEY,
    app_name VARCHAR(100) NOT NULL,
    app_version VARCHAR(50) NOT NULL,
    build_url VARCHAR(500),
    app_repo VARCHAR(200),
    deploy_env VARCHAR(20) NOT NULL,
    test_data_version VARCHAR(50),
    test_type VARCHAR(50) NOT NULL,
    test_results JSONB NOT NULL,
    tests_passed INTEGER,
    tests_failed INTEGER,
    tests_skipped INTEGER,
    test_duration_seconds INTEGER,
    date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for common queries
    CONSTRAINT test_type_check CHECK (test_type IN ('unit', 'integration', 'e2e', 'performance', 'security'))
);

CREATE INDEX idx_test_app_name ON test_data(app_name);
CREATE INDEX idx_test_env ON test_data(deploy_env);
CREATE INDEX idx_test_date ON test_data(date DESC);
CREATE INDEX idx_test_type ON test_data(test_type);
CREATE INDEX idx_test_app_env_date ON test_data(app_name, deploy_env, date DESC);

-- ============================================================================
-- NL2SQL CACHE TABLE
-- ============================================================================
CREATE TABLE nl2sql_cache (
    cache_key VARCHAR(500) PRIMARY KEY,
    sql_query TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    use_count INTEGER DEFAULT 1,
    created_by VARCHAR(100),
    metadata JSONB
);

CREATE INDEX idx_nl2sql_cache_last_used ON nl2sql_cache(last_used);
CREATE INDEX idx_nl2sql_cache_created_by ON nl2sql_cache(created_by);

-- ============================================================================
-- SAMPLE DATA: DEPLOYMENT_DATA
-- ============================================================================

-- Frontend app deployments (last 2 weeks)
INSERT INTO deployment_data (app_name, app_version, build_url, app_repo, deploy_env, rollback_version, deploy_result, deploy_duration_seconds, deployed_by, date) VALUES
-- Week 1
('frontend', 'v1.2.3', 'https://ci.example.com/frontend/build/123', 'github.com/company/frontend', 'DEV', NULL, 'SUCCESS', 145, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '13 days'),
('frontend', 'v1.2.3', 'https://ci.example.com/frontend/build/123', 'github.com/company/frontend', 'QA', NULL, 'SUCCESS', 167, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '13 days'),
('frontend', 'v1.2.4', 'https://ci.example.com/frontend/build/124', 'github.com/company/frontend', 'DEV', NULL, 'SUCCESS', 152, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '12 days'),
('frontend', 'v1.2.4', 'https://ci.example.com/frontend/build/124', 'github.com/company/frontend', 'QA', NULL, 'FAILURE', 89, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '12 days'),
('frontend', 'v1.2.4', 'https://ci.example.com/frontend/build/125', 'github.com/company/frontend', 'QA', NULL, 'SUCCESS', 178, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '11 days'),
('frontend', 'v1.2.5', 'https://ci.example.com/frontend/build/126', 'github.com/company/frontend', 'DEV', NULL, 'SUCCESS', 143, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '10 days'),
('frontend', 'v1.2.5', 'https://ci.example.com/frontend/build/126', 'github.com/company/frontend', 'STAGING', NULL, 'SUCCESS', 201, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '9 days'),
('frontend', 'v1.2.5', 'https://ci.example.com/frontend/build/126', 'github.com/company/frontend', 'PROD', NULL, 'SUCCESS', 245, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '8 days'),

-- Week 2
('frontend', 'v1.2.6', 'https://ci.example.com/frontend/build/127', 'github.com/company/frontend', 'DEV', NULL, 'SUCCESS', 138, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '6 days'),
('frontend', 'v1.2.6', 'https://ci.example.com/frontend/build/127', 'github.com/company/frontend', 'QA', NULL, 'SUCCESS', 165, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '5 days'),
('frontend', 'v1.2.6', 'https://ci.example.com/frontend/build/127', 'github.com/company/frontend', 'STAGING', NULL, 'SUCCESS', 198, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '4 days'),
('frontend', 'v1.2.6', 'https://ci.example.com/frontend/build/127', 'github.com/company/frontend', 'PROD', NULL, 'FAILURE', 123, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '3 days'),
('frontend', 'v1.2.5', 'https://ci.example.com/frontend/build/126', 'github.com/company/frontend', 'PROD', 'v1.2.6', 'SUCCESS', 189, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '3 days'),
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'DEV', NULL, 'SUCCESS', 141, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '2 days'),
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'QA', NULL, 'SUCCESS', 172, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'STAGING', NULL, 'SUCCESS', 203, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '12 hours'),

-- Backend API deployments
('api-gateway', 'v2.1.0', 'https://ci.example.com/api/build/450', 'github.com/company/api-gateway', 'DEV', NULL, 'SUCCESS', 98, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '14 days'),
('api-gateway', 'v2.1.0', 'https://ci.example.com/api/build/450', 'github.com/company/api-gateway', 'QA', NULL, 'SUCCESS', 112, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '13 days'),
('api-gateway', 'v2.1.1', 'https://ci.example.com/api/build/451', 'github.com/company/api-gateway', 'DEV', NULL, 'FAILURE', 45, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '11 days'),
('api-gateway', 'v2.1.1', 'https://ci.example.com/api/build/452', 'github.com/company/api-gateway', 'DEV', NULL, 'SUCCESS', 102, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '10 days'),
('api-gateway', 'v2.1.1', 'https://ci.example.com/api/build/452', 'github.com/company/api-gateway', 'STAGING', NULL, 'SUCCESS', 134, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '9 days'),
('api-gateway', 'v2.1.1', 'https://ci.example.com/api/build/452', 'github.com/company/api-gateway', 'PROD', NULL, 'SUCCESS', 156, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '7 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'DEV', NULL, 'SUCCESS', 95, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '5 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'QA', NULL, 'SUCCESS', 108, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '4 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'STAGING', NULL, 'SUCCESS', 128, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '3 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'PROD', NULL, 'SUCCESS', 147, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '2 days'),

-- Auth service deployments
('auth-service', 'v3.0.1', 'https://ci.example.com/auth/build/890', 'github.com/company/auth-service', 'DEV', NULL, 'SUCCESS', 67, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '10 days'),
('auth-service', 'v3.0.1', 'https://ci.example.com/auth/build/890', 'github.com/company/auth-service', 'STAGING', NULL, 'SUCCESS', 89, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '8 days'),
('auth-service', 'v3.0.1', 'https://ci.example.com/auth/build/890', 'github.com/company/auth-service', 'PROD', NULL, 'SUCCESS', 112, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '6 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/891', 'github.com/company/auth-service', 'DEV', NULL, 'SUCCESS', 71, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '4 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/891', 'github.com/company/auth-service', 'QA', NULL, 'FAILURE', 34, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '3 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/892', 'github.com/company/auth-service', 'QA', NULL, 'SUCCESS', 78, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '3 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/892', 'github.com/company/auth-service', 'STAGING', NULL, 'SUCCESS', 91, 'charlie@company.com', CURRENT_TIMESTAMP - INTERVAL '2 days'),

-- User service deployments (some recent activity)
('user-service', 'v1.8.0', 'https://ci.example.com/user/build/234', 'github.com/company/user-service', 'DEV', NULL, 'SUCCESS', 54, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '7 days'),
('user-service', 'v1.8.0', 'https://ci.example.com/user/build/234', 'github.com/company/user-service', 'PROD', NULL, 'SUCCESS', 78, 'bob@company.com', CURRENT_TIMESTAMP - INTERVAL '5 days'),
('user-service', 'v1.8.1', 'https://ci.example.com/user/build/235', 'github.com/company/user-service', 'DEV', NULL, 'SUCCESS', 56, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('user-service', 'v1.8.1', 'https://ci.example.com/user/build/235', 'github.com/company/user-service', 'QA', NULL, 'SUCCESS', 63, 'alice@company.com', CURRENT_TIMESTAMP - INTERVAL '6 hours');

-- ============================================================================
-- SAMPLE DATA: TEST_DATA
-- ============================================================================

-- Frontend tests
INSERT INTO test_data (app_name, app_version, build_url, app_repo, deploy_env, test_data_version, test_type, test_results, tests_passed, tests_failed, tests_skipped, test_duration_seconds, date) VALUES
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'DEV', 'v1.0', 'unit', '{"suites": [{"name": "Components", "passed": 45, "failed": 0}, {"name": "Utils", "passed": 23, "failed": 0}]}', 68, 0, 2, 34, CURRENT_TIMESTAMP - INTERVAL '2 days'),
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'DEV', 'v1.0', 'integration', '{"suites": [{"name": "API Integration", "passed": 12, "failed": 1}, {"name": "UI Flow", "passed": 8, "failed": 0}]}', 20, 1, 0, 89, CURRENT_TIMESTAMP - INTERVAL '2 days'),
('frontend', 'v1.2.7', 'https://ci.example.com/frontend/build/128', 'github.com/company/frontend', 'QA', 'v1.0', 'e2e', '{"suites": [{"name": "User Journeys", "passed": 15, "failed": 0}, {"name": "Critical Paths", "passed": 10, "failed": 0}]}', 25, 0, 1, 234, CURRENT_TIMESTAMP - INTERVAL '1 day'),
('frontend', 'v1.2.6', 'https://ci.example.com/frontend/build/127', 'github.com/company/frontend', 'STAGING', 'v1.0', 'performance', '{"suites": [{"name": "Load Test", "passed": 5, "failed": 2}, {"name": "Stress Test", "passed": 3, "failed": 0}]}', 8, 2, 0, 456, CURRENT_TIMESTAMP - INTERVAL '4 days'),
('frontend', 'v1.2.5', 'https://ci.example.com/frontend/build/126', 'github.com/company/frontend', 'PROD', 'v1.0', 'security', '{"suites": [{"name": "OWASP", "passed": 12, "failed": 0}, {"name": "XSS", "passed": 8, "failed": 0}]}', 20, 0, 0, 123, CURRENT_TIMESTAMP - INTERVAL '8 days'),

-- API Gateway tests
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'DEV', 'v2.0', 'unit', '{"suites": [{"name": "Routing", "passed": 34, "failed": 0}, {"name": "Middleware", "passed": 28, "failed": 1}]}', 62, 1, 3, 45, CURRENT_TIMESTAMP - INTERVAL '5 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'DEV', 'v2.0', 'integration', '{"suites": [{"name": "Service Communication", "passed": 18, "failed": 0}, {"name": "Database", "passed": 14, "failed": 0}]}', 32, 0, 1, 78, CURRENT_TIMESTAMP - INTERVAL '5 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'QA', 'v2.0', 'e2e', '{"suites": [{"name": "API Flows", "passed": 22, "failed": 0}, {"name": "Error Handling", "passed": 9, "failed": 1}]}', 31, 1, 0, 156, CURRENT_TIMESTAMP - INTERVAL '4 days'),
('api-gateway', 'v2.1.2', 'https://ci.example.com/api/build/453', 'github.com/company/api-gateway', 'STAGING', 'v2.0', 'performance', '{"suites": [{"name": "Throughput", "passed": 6, "failed": 0}, {"name": "Latency", "passed": 4, "failed": 0}]}', 10, 0, 0, 567, CURRENT_TIMESTAMP - INTERVAL '3 days'),
('api-gateway', 'v2.1.1', 'https://ci.example.com/api/build/452', 'github.com/company/api-gateway', 'PROD', 'v2.0', 'security', '{"suites": [{"name": "Authentication", "passed": 15, "failed": 0}, {"name": "Authorization", "passed": 12, "failed": 0}]}', 27, 0, 0, 89, CURRENT_TIMESTAMP - INTERVAL '7 days'),

-- Auth service tests
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/892', 'github.com/company/auth-service', 'DEV', 'v1.5', 'unit', '{"suites": [{"name": "Token Generation", "passed": 23, "failed": 0}, {"name": "Validation", "passed": 19, "failed": 0}]}', 42, 0, 1, 28, CURRENT_TIMESTAMP - INTERVAL '3 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/892', 'github.com/company/auth-service', 'QA', 'v1.5', 'integration', '{"suites": [{"name": "OAuth Flow", "passed": 8, "failed": 0}, {"name": "Session Management", "passed": 6, "failed": 0}]}', 14, 0, 0, 67, CURRENT_TIMESTAMP - INTERVAL '3 days'),
('auth-service', 'v3.0.2', 'https://ci.example.com/auth/build/892', 'github.com/company/auth-service', 'STAGING', 'v1.5', 'security', '{"suites": [{"name": "Encryption", "passed": 10, "failed": 0}, {"name": "Brute Force", "passed": 5, "failed": 0}]}', 15, 0, 0, 145, CURRENT_TIMESTAMP - INTERVAL '2 days'),
('auth-service', 'v3.0.1', 'https://ci.example.com/auth/build/890', 'github.com/company/auth-service', 'PROD', 'v1.5', 'e2e', '{"suites": [{"name": "Login Flow", "passed": 12, "failed": 0}, {"name": "Logout Flow", "passed": 8, "failed": 0}]}', 20, 0, 0, 98, CURRENT_TIMESTAMP - INTERVAL '6 days'),

-- User service tests
('user-service', 'v1.8.1', 'https://ci.example.com/user/build/235', 'github.com/company/user-service', 'DEV', 'v1.0', 'unit', '{"suites": [{"name": "User CRUD", "passed": 28, "failed": 1}, {"name": "Profile", "passed": 15, "failed": 0}]}', 43, 1, 2, 31, CURRENT_TIMESTAMP - INTERVAL '1 day'),
('user-service', 'v1.8.1', 'https://ci.example.com/user/build/235', 'github.com/company/user-service', 'QA', 'v1.0', 'integration', '{"suites": [{"name": "Database", "passed": 16, "failed": 0}, {"name": "Cache", "passed": 9, "failed": 0}]}', 25, 0, 1, 54, CURRENT_TIMESTAMP - INTERVAL '6 hours'),
('user-service', 'v1.8.0', 'https://ci.example.com/user/build/234', 'github.com/company/user-service', 'PROD', 'v1.0', 'e2e', '{"suites": [{"name": "Registration", "passed": 10, "failed": 0}, {"name": "Profile Update", "passed": 8, "failed": 0}]}', 18, 0, 0, 87, CURRENT_TIMESTAMP - INTERVAL '5 days');

-- ============================================================================
-- SAMPLE CACHE ENTRIES (showing what gets cached over time)
-- ============================================================================

INSERT INTO nl2sql_cache (cache_key, sql_query, created_at, last_used, use_count, created_by, metadata) VALUES
(
    'SELECT:deployment_data:frontend:*:weeks:1:*',
    'SELECT * FROM deployment_data WHERE app_name = ''frontend'' AND date >= CURRENT_DATE - INTERVAL ''1 week'' ORDER BY date DESC',
    CURRENT_TIMESTAMP - INTERVAL '10 days',
    CURRENT_TIMESTAMP - INTERVAL '2 hours',
    45,
    'alice@company.com',
    '{"result_count": 15, "timestamp": "2024-01-10T10:30:00"}'
),
(
    'SELECT:deployment_data:*:PROD:weeks:1:*',
    'SELECT * FROM deployment_data WHERE deploy_env = ''PROD'' AND date >= CURRENT_DATE - INTERVAL ''1 week'' ORDER BY date DESC',
    CURRENT_TIMESTAMP - INTERVAL '8 days',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    23,
    'bob@company.com',
    '{"result_count": 8, "timestamp": "2024-01-12T14:20:00"}'
),
(
    'COUNT:deployment_data:*:*:months:1:*',
    'SELECT COUNT(*) FROM deployment_data WHERE date >= CURRENT_DATE - INTERVAL ''1 month''',
    CURRENT_TIMESTAMP - INTERVAL '7 days',
    CURRENT_TIMESTAMP - INTERVAL '3 hours',
    18,
    'charlie@company.com',
    '{"result_count": 1, "timestamp": "2024-01-13T09:15:00"}'
),
(
    'SELECT_LATEST:deployment_data:api-gateway:PROD:*:5',
    'SELECT * FROM deployment_data WHERE app_name = ''api-gateway'' AND deploy_env = ''PROD'' ORDER BY date DESC LIMIT 5',
    CURRENT_TIMESTAMP - INTERVAL '5 days',
    CURRENT_TIMESTAMP - INTERVAL '4 hours',
    12,
    'alice@company.com',
    '{"result_count": 5, "timestamp": "2024-01-15T11:45:00"}'
),
(
    'SELECT:test_data:frontend:*:days:7:*',
    'SELECT * FROM test_data WHERE app_name = ''frontend'' AND date >= CURRENT_DATE - INTERVAL ''7 day'' ORDER BY date DESC',
    CURRENT_TIMESTAMP - INTERVAL '3 days',
    CURRENT_TIMESTAMP - INTERVAL '1 hour',
    8,
    'bob@company.com',
    '{"result_count": 12, "timestamp": "2024-01-17T08:30:00"}'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify data was inserted
SELECT 'Deployment Count' as metric, COUNT(*) as value FROM deployment_data
UNION ALL
SELECT 'Test Count' as metric, COUNT(*) as value FROM test_data
UNION ALL
SELECT 'Cache Entries' as metric, COUNT(*) as value FROM nl2sql_cache;

-- Summary by app
SELECT 
    app_name,
    COUNT(*) as total_deployments,
    SUM(CASE WHEN deploy_result = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN deploy_result = 'FAILURE' THEN 1 ELSE 0 END) as failed
FROM deployment_data
GROUP BY app_name
ORDER BY app_name;

-- Recent activity
SELECT 
    app_name,
    deploy_env,
    app_version,
    deploy_result,
    date
FROM deployment_data
WHERE date >= CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY date DESC
LIMIT 10;

-- Test summary
SELECT 
    app_name,
    test_type,
    COUNT(*) as test_runs,
    SUM(tests_passed) as total_passed,
    SUM(tests_failed) as total_failed
FROM test_data
GROUP BY app_name, test_type
ORDER BY app_name, test_type;