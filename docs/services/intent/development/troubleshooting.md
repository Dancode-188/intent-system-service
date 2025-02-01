# Intent Service Troubleshooting Guide

## Table of Contents
1. [Common Issues](#common-issues)
2. [Debug Procedures](#debug-procedures)
3. [Performance Issues](#performance-issues)
4. [Error Handling](#error-handling)
5. [Log Analysis](#log-analysis)
6. [Recovery Procedures](#recovery-procedures)

## Common Issues

### Database Connection Issues

#### Neo4j Connection Failures
**Symptoms:**
- Service health check returns "neo4j: down"
- Logs show `ServiceUnavailable` or `SessionExpired` exceptions
- Pattern operations failing with database errors

**Troubleshooting Steps:**
1. Check Neo4j container status:
   ```bash
   docker ps | grep neo4j
   ```
2. Verify Neo4j credentials and connection string in environment variables
3. Check Neo4j logs:
   ```bash
   docker logs intent-neo4j
   ```
4. Verify network connectivity:
   ```bash
   telnet localhost 7687
   ```

**Resolution:**
- Restart Neo4j container if unhealthy
- Check for memory pressure and increase if needed
- Verify connection pool settings in config.py

#### Redis Connection Issues
**Symptoms:**
- Rate limiting not working
- Cache misses for all requests
- Redis connection errors in logs

**Troubleshooting Steps:**
1. Check Redis container status
2. Verify Redis connection:
   ```bash
   redis-cli ping
   ```
3. Check Redis memory usage:
   ```bash
   redis-cli info memory
   ```

**Resolution:**
- Adjust Redis connection pool size
- Clear Redis cache if corrupted
- Check for memory leaks

### Service Health Issues

#### High Error Rates
**Symptoms:**
- Increased 500 status codes
- Error rate metric spike in Prometheus
- Multiple error logs

**Troubleshooting Steps:**
1. Check recent deployments
2. Review error logs:
   ```bash
   grep ERROR /var/log/intent-service/app.log | tail -n 100
   ```
3. Verify dependent services health

**Resolution:**
- Rollback recent changes if correlated
- Scale service if under load
- Clear caches if data corruption suspected

## Debug Procedures

### Local Debugging

1. Enable Debug Mode
   ```bash
   export INTENT_DEBUG=True
   ```

2. Increase Log Level
   ```bash
   export INTENT_LOG_LEVEL=DEBUG
   ```

3. Use Debug Endpoints
   ```bash
   curl http://localhost:8000/debug/state
   ```

### Production Debugging

1. Enable Enhanced Logging Temporarily
   ```bash
   curl -X POST http://localhost:8000/admin/logging/debug
   ```

2. Collect Diagnostics
   ```bash
   ./scripts/collect-diagnostics.sh
   ```

3. Analyze Metrics
   ```bash
   curl http://localhost:8000/metrics
   ```

## Performance Issues

### Slow Response Times

**Symptoms:**
- High latency in monitoring
- Request timeouts
- Increased queue length

**Investigation:**
1. Check Resource Usage
   ```bash
   top -p $(pgrep -f intent-service)
   ```

2. Monitor Database Performance
   ```bash
   EXPLAIN MATCH (n:Pattern) RETURN n LIMIT 1
   ```

3. Review Slow Queries
   ```bash
   grep "Slow query detected" /var/log/intent-service/app.log
   ```

**Resolution:**
- Optimize database queries
- Increase cache utilization
- Scale horizontally if needed

### Memory Leaks

**Symptoms:**
- Increasing memory usage over time
- OOM errors
- Degraded performance

**Investigation:**
1. Monitor Memory Usage
   ```bash
   ps -o pid,rss,command -p $(pgrep -f intent-service)
   ```

2. Check Memory Profile
   ```python
   from memory_profiler import profile
   ```

3. Review Object References
   ```python
   import gc
   gc.collect()
   ```

**Resolution:**
- Fix memory leaks in code
- Adjust garbage collection
- Implement memory limits

## Error Handling

### Common Error Patterns

#### MLServiceError
**Cause:** ML model operations failing
**Investigation:**
- Check model loading logs
- Verify input data format
- Check available GPU/CPU resources

#### PatternError
**Cause:** Pattern recognition failures
**Investigation:**
- Verify pattern data integrity
- Check vector store status
- Review pattern confidence scores

#### DatabaseError
**Cause:** Database operation failures
**Investigation:**
- Check database connectivity
- Review query performance
- Verify data consistency

#### RateLimitError
**Cause:** Rate limit exceeded
**Investigation:**
- Check rate limit configuration
- Review client usage patterns
- Verify Redis rate limiter status

## Log Analysis

### Log Locations
- Application Logs: `/var/log/intent-service/app.log`
- Access Logs: `/var/log/intent-service/access.log`
- Error Logs: `/var/log/intent-service/error.log`

### Common Log Patterns

#### Pattern Processing
```
PATTERN_PROCESSING pattern_id=<id> confidence=<score> type=<type>
```

#### Database Operations
```
DB_OPERATION operation=<op> duration=<ms> success=<bool>
```

#### Rate Limiting
```
RATE_LIMIT client=<id> limit=<n> remaining=<n>
```

### Log Analysis Tools
1. Basic Analysis
   ```bash
   grep -r "ERROR" /var/log/intent-service/
   ```

2. Advanced Analysis
   ```bash
   awk '/ERROR/ {print $1, $4}' app.log | sort | uniq -c
   ```

3. Real-time Monitoring
   ```bash
   tail -f app.log | grep --line-buffered "ERROR"
   ```

## Recovery Procedures

### Service Recovery

1. **Quick Recovery**
   ```bash
   ./scripts/recover-service.sh
   ```
   - Restarts service
   - Verifies health
   - Restores connections

2. **Full Recovery**
   ```bash
   ./scripts/full-recovery.sh
   ```
   - Stops service
   - Clears caches
   - Rebuilds indexes
   - Restarts service

### Data Recovery

1. **Pattern Data**
   ```bash
   ./scripts/recover-patterns.sh
   ```
   - Verifies pattern integrity
   - Rebuilds corrupted patterns
   - Updates vector store

2. **Graph Recovery**
   ```bash
   ./scripts/recover-graph.sh
   ```
   - Checks graph consistency
   - Repairs relationships
   - Rebuilds indices

### Emergency Procedures

1. **Service Shutdown**
   ```bash
   ./scripts/emergency-shutdown.sh
   ```
   - Graceful connection termination
   - State preservation
   - Client notification

2. **Emergency Restore**
   ```bash
   ./scripts/emergency-restore.sh
   ```
   - Data consistency check
   - Service restoration
   - Client reconnection

### Monitoring Recovery

1. Monitor Service Health
   ```bash
   watch -n 1 curl -s http://localhost:8000/health
   ```

2. Verify Metrics
   ```bash
   curl http://localhost:8000/metrics | grep intent_service
   ```

3. Check Recovery Logs
   ```bash
   tail -f /var/log/intent-service/recovery.log
   ```

## Contact and Escalation

### Support Levels

1. **Level 1: Development Team**
   - Email: dev-team@company.com
   - Slack: #intent-service-dev

2. **Level 2: Service Operations**
   - Email: sre-team@company.com
   - Pager: +1-555-0123

3. **Level 3: Emergency Response**
   - Hotline: +1-555-0911
   - Slack: #intent-service-911

### When to Escalate
- Service down > 5 minutes
- Error rate > 10%
- Data corruption detected
- Security breach suspected