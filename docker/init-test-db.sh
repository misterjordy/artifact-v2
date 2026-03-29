#!/bin/bash
psql -U artifact -d artifact_db -c "SELECT 1" && \
psql -U artifact -c "CREATE DATABASE artifact_test OWNER artifact;" 2>/dev/null || true
