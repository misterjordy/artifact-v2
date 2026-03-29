# Incident Response Runbook — artiFACT

## SITE IS DOWN

1. SSH to VPS: `ssh artifact-vps`
2. Check containers: `docker compose ps`
   - If containers are stopped: `docker compose up -d`
   - If containers are restarting: `docker compose logs -f web` (check for crash loop)
3. Check nginx: `sudo systemctl status nginx`
   - If nginx is down: `sudo systemctl restart nginx`
4. Check disk: `df -h` (if >90%, clear docker images: `docker system prune`)
5. Check memory: `free -h` (if <200MB free, restart stack: `docker compose restart`)

## SITE IS SLOW

1. `docker compose logs -f web` — look for slow query warnings
2. `docker compose exec web python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"`
3. `docker compose exec postgres psql -U artifact -c "SELECT count(*) FROM pg_stat_activity"`
4. If Postgres connections maxed: `docker compose restart postgres`

## USER REPORTS SEEING WRONG DATA

1. Check permission cache: flush immediately
   ```
   docker compose exec web python -c "
   import redis; r=redis.from_url('$REDIS_URL');
   keys = r.keys('perm:*'); r.delete(*keys) if keys else None;
   print(f'Flushed {len(keys)} permission cache entries')"
   ```
2. Check user's grants: `SELECT * FROM fc_node_permission WHERE user_uid = 'XXX'`
3. Check event_log for recent changes: `SELECT * FROM fc_event_log ORDER BY occurred_at DESC LIMIT 20`

## USER'S AI KEY LEAKED

1. The leaked key is the USER'S key (OpenAI/Anthropic), not ours
2. Tell user to rotate their key on the provider's website immediately
3. User saves new key in artiFACT Settings -> old encrypted blob overwritten
4. If our MASTER encryption key is compromised (Secrets Manager):
   - Generate new master key in Secrets Manager
   - Run: `python scripts/rotate_master_key.py --old-key-arn ARN --new-key-arn ARN`
   - This decrypts all user keys with old master, re-encrypts with new master
   - Update ECS task definition with new Secrets Manager ARN
   - Redeploy

## DATABASE CORRUPTED

**On VPS:**
```
docker compose down
docker compose exec postgres pg_restore -U artifact -d artifact_db backup_YYYYMMDD.sql
docker compose up -d
docker compose exec web alembic upgrade head
```

**On COSMOS:**
```
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier artifact-prod \
  --target-db-instance-identifier artifact-prod-restored \
  --restore-time "2026-03-28T15:00:00Z"
```
Update ECS environment to point to restored instance. Verify data, then rename instances.

## HOW TO ROLL BACK A BAD DEPLOY

**On VPS:**
```
git log --oneline -5          # find last good commit
git checkout <good-sha>
docker compose up --build -d
```

**On COSMOS:**
```
# ECS auto-rolls-back if health checks fail
# Manual: update task definition to previous image tag
aws ecs update-service --cluster artifact --service web \
  --task-definition artifact-web:PREVIOUS_REVISION
```

## ANOMALY DETECTED

1. Check admin dashboard or `fc_event_log` for `entity_type='anomaly'`
2. User sessions already auto-expired by anomaly detector
3. Review the flagged user's recent activity in audit log
4. If malicious: deactivate user via admin panel
5. If false positive: no action needed, user re-authenticates via CAC
