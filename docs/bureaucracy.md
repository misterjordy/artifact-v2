# artiFACT — Bureaucracy Checklist

**Purpose**: Every non-engineering task needed to keep gatekeepers from blocking your deployment. Ordered by urgency — top items will block you soonest.

---

## 1. COSMOS SORN Coverage (DO THIS WEEK)

**What**: Determine if COSMOS's existing System of Records Notice covers tenant applications.

**Why**: artiFACT stores PII (EDIPI, display name, email). If COSMOS's SORN covers all apps running on its platform, you inherit it and this line item is closed. If it doesn't, you need your own SORN, which takes 4-6 months (Federal Register publication + 30-day public comment period).

**How**:
```
1. Email the COSMOS PM (Heather Heben) or your COSMOS POC:
   
   Subject: SORN coverage for artiFACT on COSMOS
   
   "Our application (artiFACT) stores minimal PII derived from CAC 
   authentication: display name, email, and EDIPI. We do not collect 
   PII via forms — it's all inherited from the COSMOS SAML assertion.
   
   Does the COSMOS authorization boundary's SORN cover tenant 
   applications that store CAC-derived PII? Or do we need a 
   separate SORN for artiFACT?"

2. If COSMOS SORN covers you:
   → Document the SORN number and coverage in your SSP
   → Done

3. If COSMOS SORN does NOT cover you:
   → Contact your command Privacy Officer
   → Request they initiate a SORN through DON CIO
   → Timeline: 4-6 months (Federal Register publication + comment period)
   → In the meantime: you can operate under COSMOS's IATT/ATO 
     but the SORN gap should be documented in your POA&M 
     (which you're not doing, but the AO may require it)
```

**Time**: 1 email, 1 day wait for response.

---

## 2. Privacy Impact Assessment (WITHIN 2 WEEKS)

**What**: A PIA documents what PII you collect, why, and how you protect it. Required by the E-Government Act of 2002 for any federal system that collects PII.

**Why**: Your AO will ask for it. If you don't have one, they can't authorize you.

**How**:
```
1. Get the DON PIA template from your command Privacy Officer
   (or download from DON CIO website)

2. Fill it out. For artiFACT, most answers are short:

   Q: What PII do you collect?
   A: Display name, email address, EDIPI (DoD ID number), CAC 
      Distinguished Name. All derived from the COSMOS SAML assertion
      at login. No PII is collected via user input forms.

   Q: Why do you collect it?
   A: To identify users for role-based access control, audit logging, 
      and accountability. The system must know who approved, rejected, 
      and signed each fact.

   Q: How is it stored?
   A: PostgreSQL database encrypted at rest (RDS AES-256). EDIPI and 
      CAC DN are indexed for lookup. No SSNs, no financial data, no 
      medical data.

   Q: Who has access?
   A: Admins can view user list (name, email, role). Non-admin users 
      see display names only (on approval/signature records). No user 
      can see another user's EDIPI.

   Q: How long is it retained?
   A: User records are retained for the life of the system. Deactivated 
      users are soft-deleted (is_active=false) to preserve audit trail 
      integrity. Hard deletion available by admin request.

   Q: Is PII shared externally?
   A: The Advana sync API can include display names and roles (not EDIPI) 
      for authenticated service accounts. No PII is shared with 
      commercial services. AI API calls (Bedrock) do not include PII.

3. Submit to your command Privacy Officer for review and approval.
4. Attach the approved PIA to your RMF package.
```

**Time**: 2-3 hours to fill out, 1-2 weeks for review/approval.

---

## 3. DITPR Registration (WITHIN 30 DAYS)

**What**: Register artiFACT in the DoD IT Portfolio Repository. This is the master list of all DoD IT systems.

**Why**: Without DITPR registration, your system officially "doesn't exist" in the DoD IT inventory. Auditors, enterprise architects, and budget analysts all check DITPR.

**How**:
```
1. Access DITPR at https://ditpr.osd.mil (CAC required)

2. Create a new system entry with:
   - System Name: artiFACT
   - System Acronym: ARTIFACT
   - Description: "Taxonomy-driven atomic fact corpus platform for 
     managing, versioning, and generating DoD software acquisition 
     engineering documentation. Decomposes traditional acquisition 
     documents into atomic, version-controlled, signable facts 
     organized in a hierarchical taxonomy."
   - System Type: Major Application
   - Classification: UNCLASSIFIED // CUI
   - Impact Level: IL-4/5
   - Hosting: COSMOS (NIWC Pacific Cloud Service Center)
   - Cloud Service Provider: AWS GovCloud
   - Responsible Organization: NAVWAR / [your PMW/PMO code]
   - Program Manager: Jordan Allred
   - Funding Source: [your WBS/charge code]
   - ATO Status: Planned (update when granted)
   - Users: DON program managers, engineers, acquisition professionals

3. Save and note the DITPR ID number.
4. Reference the DITPR ID in your SSP and any acquisition documents.
```

**Time**: 1-2 hours to fill out, instant registration.

---

## 4. Records Retention Schedule (WITHIN 60 DAYS)

**What**: Map your system's data to a NARA-approved records retention schedule.

**Why**: Federal records law (44 USC Chapter 31) requires that federal records follow an approved disposition schedule. Your fact versions, approval decisions, and signatures are federal records.

**How**:
```
1. Contact your command Records Manager (every Navy command has one)

2. Propose the following mapping:

   artiFACT Data Type              → NARA Schedule         → Retention
   ─────────────────────────────────────────────────────────────────────
   Fact versions + approval        → GRS 5.2, Item 020     → 3 years after
   decisions (fc_fact_version,       (Input/source records    version is
   fc_event_log approvals)           for electronic systems)  superseded or
                                                              system is retired
   
   Audit trail                     → GRS 3.2, Item 031     → 6 years
   (fc_event_log full)               (Security and access 
                                      control records)
   
   Signature records               → GRS 5.2, Item 020     → 3 years after
   (fc_signature)                    (Input/source records)   superseded
   
   User feedback                   → GRS 5.7, Item 010     → 1 year after
   (fc_feedback)                     (Customer service        resolved
                                      records)
   
   Import sessions                 → GRS 5.2, Item 020     → 90 days after
   (fc_import_session)                                        completion
   
   System config +                 → GRS 3.1, Item 010     → Delete when
   feature flags                     (Technology              superseded
   (fc_system_config)                 management records)

3. Get Records Manager approval (signature or email confirmation)

4. Update your data retention policy (architecture doc section 10.3)
   to align with approved schedule. If the Records Manager says 
   "audit trail is permanent" — change the 2-year archive-to-S3 
   to "archive to S3, never delete."

5. Document the approved schedule in your SSP.
```

**Time**: 1 meeting + 1-2 emails, 2-4 weeks for approval.

---

## 5. Collibra Data Catalog Registration (WHEN ADVANA INTEGRATION IS ACTIVE)

**What**: Register artiFACT as a data source in Advana's Collibra data catalog.

**Why**: The DON CDO wants all data sources discoverable in Jupiter/Advana. If you're feeding data to Advana via the sync API, the data needs metadata in Collibra.

**How**:
```
1. Contact the Jupiter team (jupiter@navy.mil or your command's 
   Data Officer / MADO)

2. Provide:
   - Data Source Name: artiFACT Fact Corpus
   - Owner: [your organization]
   - Data Steward: Jordan Allred
   - Classification: CUI
   - Refresh Frequency: Near-real-time (delta feed API, polled by Advana)
   - Data Format: JSON via REST API (OpenAPI 3.0 spec available)
   - API Endpoint: https://artifact.cosmos.navy.mil/api/v1/openapi.json
   - Data Elements: nodes (taxonomy), facts (atomic statements), 
     versions (change history), signatures (attestation records)
   - Quality Score: High (every fact is human-reviewed and approved)

3. Jupiter team registers the source in Collibra and configures 
   their Apigee gateway to pull from your sync endpoints.
```

**Time**: 1 meeting + 1 form, depends on Jupiter team's queue.

---

## 6. CUI Training Verification (BEFORE PRODUCTION USERS)

**What**: Verify that all artiFACT users have current CUI training.

**Why**: DoD policy requires anyone accessing CUI to have completed CUI awareness training.

**What you DON'T need to do**: Build a training-check feature into artiFACT. CUI training compliance is a command responsibility, not an application responsibility.

**What you DO need to do**:
```
1. Add this sentence to your user agreement / splash screen:
   "By accessing this system, you certify that you have completed 
   current DoD CUI Awareness Training."

2. Document in your SSP:
   "CUI training compliance is enforced administratively by 
   user commands. artiFACT does not independently verify 
   training completion. All users are authenticated via DoD CAC, 
   which requires active duty/civilian/contractor status with 
   a sponsoring command responsible for training compliance."

3. Done. If someone pushes for an automated training check, 
   point them to the COSMOS onboarding process, which already 
   verifies CAC + US citizenship. Training verification is their 
   command's job, not your application's job.
```

**Time**: 5 minutes (add one sentence to splash screen).

---

## 7. OWASP ZAP Scan Results (SPRINT 13)

**What**: Run an automated dynamic application security test.

**Why**: The ISSM/SCA will want to see application-level vulnerability scan results alongside the cloud-level Wiz scans.

**How**: Already in Sprint 13 CI pipeline. Run it, fix HIGHs/MEDIUMs, attach the report to your RMF package.

**Time**: Already baked into Sprint 13.

---

## TRACKING TABLE

| Item | Owner | Deadline | Status |
|------|-------|----------|--------|
| COSMOS SORN coverage | Jordan → COSMOS PM | This week | ☐ Not started |
| Privacy Impact Assessment | Jordan → Privacy Officer | 2 weeks | ☐ Not started |
| DITPR registration | Jordan | 30 days | ☐ Not started |
| Records retention schedule | Jordan → Records Manager | 60 days | ☐ Not started |
| Collibra registration | Jordan → Jupiter team | When Advana feed active | ☐ Not started |
| CUI training splash text | Jordan | Sprint 1 | ☐ Not started |
| ZAP scan results | CI pipeline | Sprint 13 | ☐ Not started |
