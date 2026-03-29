# artiFACT — Canned Q&A

**Purpose**: Ready-made answers for every objection, question, and concern that government stakeholders will raise. Organized by the type of person asking.

---

## ACQUISITION & CONTRACTING

**Q: What's the acquisition pathway?**

artiFACT follows the DoD Software Acquisition Pathway under the Adaptive Acquisition Framework. It's developed internally by a NAVWAR program office using existing government labor — there is no contract vehicle, no ACAT designation, and no milestone decision authority required. COSMOS hosting is a consumption-based cloud service provisioned through NIWC Pacific, not a separate procurement. The entire stack is FOSS (Free and Open Source Software) with zero commercial license costs.

**Q: Is this a program of record?**

No, and it doesn't need to be. artiFACT is an internal productivity tool — it helps program offices manage the facts that go into their acquisition documents. It's not a weapons system, not a business system, and not an enterprise IT service. It's analogous to a team using a shared database instead of passing Word documents around. If leadership wants to elevate it to a program of record in the future, the architecture, documentation, and ATO artifacts are already in place to support that transition.

**Q: Who sustains this when you PCS?**

The codebase is fully documented: architecture document, master reference with style guides and pseudocode, 15 sprint files with definitions of success, and an OpenAPI spec. Any developer proficient in Python and FastAPI can pick it up. COSMOS hosting costs are approximately $175/month — trivially fundable from any program office's IT budget. The system runs unattended between deployments (no babysitting). A named backup PM should be designated before production deployment.

**Q: What's the total cost?**

Development: existing government labor (no contract cost). Hosting: ~$175/mo on COSMOS ($2,100/yr). Software licenses: $0 (all FOSS). AI costs: per-user — each user provides their own Amazon Bedrock API key, billed to their organization. Total sustainment cost: under $3,000/year excluding labor.

---

## ENTERPRISE ARCHITECTURE & INTEROPERABILITY

**Q: How does this fit into the DON enterprise architecture?**

artiFACT feeds data to Jupiter/Advana via a standard REST API with an OpenAPI 3.0 specification. Advana's Apigee gateway discovers the spec automatically. The delta feed uses a monotonic cursor for incremental sync. artiFACT is a data *producer* in the DON data mesh — it creates authoritative atomic facts that Advana can ingest, query, and visualize alongside other DON data sources.

**Q: Why not just use SharePoint? Or Confluence? Or DOORS?**

Those tools store *documents*. artiFACT stores *atomic facts*. You cannot version-control a single sentence in SharePoint. You cannot programmatically generate a Systems Engineering Plan from a Confluence wiki. You cannot sign individual statements in DOORS. You cannot API-feed atomic facts to Advana from any of those platforms. artiFACT decomposes documents into their smallest meaningful unit — a single factual statement — and manages each one with version control, approval workflows, digital signatures, and AI-assisted generation. The documents are the *output*, not the *input*.

**Q: Does this work on NMCI / Flank Speed?**

artiFACT is a web application hosted on COSMOS (AWS GovCloud). It is accessible from any CAC-enabled browser on commercial internet or DODIN. NMCI users may need a proxy exception for `*.cosmos.navy.mil` — contact your NMCI support desk. Flank Speed users can access it directly. artiFACT is not available on SIPR or JWICS — it processes CUI (IL-4/5), not classified information.

**Q: Can I access it from my phone / tablet?**

If your device has a CAC reader and a browser, yes. The UI is responsive. However, DoD mobile device policy applies — access from personally-owned devices is subject to your command's BYOD policy and COSMOS's access requirements.

**Q: How does this integrate with [other system]?**

artiFACT exposes a complete REST API with an auto-generated OpenAPI 3.0 spec at `/api/v1/openapi.json`. Any system that can consume a REST API can integrate. For Advana/Jupiter specifically, there's a purpose-built delta feed endpoint. For other systems, the standard CRUD endpoints cover all data. API keys provide machine-to-machine authentication with scoped permissions.

---

## SECURITY & COMPLIANCE

**Q: What's the ATO status?**

artiFACT will operate under COSMOS's authorization boundary. COSMOS has an existing ATO through NIWC Pacific. artiFACT's application-specific security controls (RBAC, CSRF, encryption, audit logging, ZT compliance) are documented in the SSP skeleton and will be assessed as part of the COSMOS tenant onboarding process. The target is a continuous ATO (cATO) leveraging the DevSecOps pipeline (SBOM, pip-audit, ZAP scan, automated tests in CI).

**Q: Is this Zero Trust compliant?**

Yes. artiFACT addresses all seven pillars of the DoD Zero Trust Reference Architecture v2.0. Pillars 2 (Device) and 3 (Network) are inherited from COSMOS's CNAP/Netskope infrastructure. artiFACT implements: CAC multi-factor authentication with 15-minute session re-validation (Pillar 1), non-root containers with input validation and SBOM tracking (Pillar 4), per-fact classification with CUI markings and read-access logging (Pillar 5), structured log forwarding and anomaly detection (Pillar 6), and automated session expiration on anomalous behavior (Pillar 7).

**Q: How do you handle CUI?**

All data at rest is encrypted (RDS AES-256, S3 SSE, AI keys AES-256-GCM). All data in transit uses TLS 1.2+. AI processing uses Amazon Bedrock in AWS GovCloud (IL-4/5 authorized) — CUI never leaves the authorization boundary. Generated documents automatically include CUI banners (header/footer) when any included fact has a CUI classification. Per-fact classification fields enable granular CUI tracking.

**Q: Where's the ConOps / SDD / security documentation?**

artiFACT generates its own compliance documentation from its own corpus. The system ships with a pre-loaded "artiFACT" program containing atomic facts about its architecture, security controls, data flows, and capabilities. ConOps and SDD document templates are pre-configured. Selecting a template and clicking "Generate" produces a current, formatted DOCX. The documentation is always up-to-date because it's generated from the same facts that are maintained in the system.

**Q: Who did the security assessment?**

Application-level: automated testing in CI (OWASP ZAP dynamic scan, pip-audit dependency scan, SBOM generation, 80%+ test coverage including security regression tests for all 110 v1 findings). Cloud-level: COSMOS provides Wiz for infrastructure scanning and RegScale for RMF artifact management. The combined evidence package supports the ATO assessment.

---

## DATA & PRIVACY

**Q: What PII do you collect?**

Display name, email address, EDIPI (DoD ID number), and CAC Distinguished Name. All derived from the COSMOS SAML assertion at login — nothing is collected via user input forms. No SSNs, no financial data, no medical data, no biometrics.

**Q: Where's the Privacy Impact Assessment?**

In progress. artiFACT's PII footprint is minimal and entirely CAC-derived. The PIA is being coordinated through the command Privacy Officer. COSMOS's existing SORN coverage for tenant applications is being verified — if it covers artiFACT, no separate SORN is needed.

**Q: Can I get all my data out?**

Yes, immediately. `GET /api/v1/sync/full` returns every node, fact, version, signature, user record, and audit event as a single JSON payload. Additionally, fact exports are available in TXT, JSON, NDJSON, and CSV formats. Generated DOCX documents are downloadable with signed URLs. There is zero data lock-in.

**Q: Is this registered in Collibra / the data catalog?**

Registration will occur when the Advana delta feed is active. The data source metadata (owner, classification, refresh frequency, data elements, API endpoint) is already documented and ready for Collibra submission.

**Q: What happens to the data if artiFACT shuts down?**

Run `/api/v1/sync/full` → download the JSON archive → load into any database or data warehouse. The export includes the complete taxonomy structure, all fact versions with full history, all signatures, and the complete audit trail. The data format is self-describing (JSON with clear field names and types). No proprietary encoding.

---

## TRAINING & DOCUMENTATION

**Q: Where's the user training plan?**

artiFACT includes a built-in interactive presentation module with narrated slides, beat-driven progression, and a guided tour that walks users through every feature. A "teach mode" provides hands-on tutorials for common workflows (create a fact, approve a proposal, sign a node). No separate LMS course or classroom training is required. CUI awareness training is a command responsibility, not an application feature.

**Q: Do users need DD Form 2875 (System Access Request)?**

Check with your command's ISSM. COSMOS may handle system access through its own onboarding process (CAC + US citizenship verification). If your command requires DD 2875s for tenant applications on COSMOS, the form fields are: System Name = artiFACT, Classification = CUI, Access Level = [role], Justification = [one sentence about their program management duties].

**Q: Where's the documentation? I need a ConOps, an SDD, an OV-1.**

artiFACT generates its own documentation. The system contains atomic facts about its own architecture, security, and operations. Pre-configured document templates (ConOps, SDD) produce formatted DOCX documents on demand. The architecture document, master reference, and 15 sprint files collectively contain more technical detail than a traditional SDD — they're available for download. If a specific format is required, the facts can be regenerated into any template.

---

## BUDGET & SUSTAINMENT

**Q: What does the comptroller need to know?**

Annual sustainment cost: approximately $2,100 for COSMOS hosting (consumption-based, no commitment). Zero license fees. AI costs are per-user (each user's organization pays for their own Bedrock usage — typically $5-50/month depending on usage). No contractor support required for daily operations. The system runs unattended between deployments.

**Q: What if funding is cut?**

Export all data via `/api/v1/sync/full`. Cancel the COSMOS account. The data lives on as a JSON archive. If funding is restored, stand up a new COSMOS environment, import the archive, and resume operations. Total recovery time: approximately 1 day.

**Q: Is there a vendor dependency?**

No. The entire stack is FOSS: Python, FastAPI, PostgreSQL, Redis, Docker. There is no vendor, no license, no SaaS subscription, and no commercial support contract. The source code is government-owned. Amazon Bedrock is used for AI features but is not required for core operations — fact management, approval workflows, signing, and export all work without AI.

---

## THE SKEPTICS

**Q: This seems like a solution looking for a problem.**

71 engineering artifacts across a typical DoD acquisition program carry over 30% duplicative content. When a single fact changes (e.g., "the system operates at IL-5"), a human must manually find and update every document that contains that fact. artiFACT stores the fact once, in one place, with version control and approval workflows. Documents are generated on demand from the current corpus. The problem is real, documented, and costs thousands of engineering hours across the DON.

**Q: How is this different from what [specific person] is building?**

artiFACT is the only system that treats individual factual statements as first-class entities with version control, approval workflows, digital signatures, classification markings, and AI-assisted document generation. Most other tools digitize *documents* or manage *requirements*. artiFACT manages *facts* — the atomic units of truth that documents are made of.

**Q: What if nobody uses it?**

The two demo programs (Boatwing and SNIPE-B) ship as playgrounds accessible to all users. New users can explore, create facts, run AI queries, and generate documents without affecting real program data. The interactive tour and teach mode provide zero-friction onboarding. Adoption risk is mitigated by the fact that artiFACT doesn't replace existing workflows — it supplements them. Users can continue using Word documents while gradually building their corpus.

**Q: This will never get an ATO.**

COSMOS exists specifically to reduce ATO friction for DON applications. The platform provides inherited security controls, automated scanning (Wiz), RMF artifact management (RegScale), and a pre-authorized cloud environment. artiFACT's application-level security is documented, tested, and auditable. The DevSecOps pipeline (SBOM, dependency scanning, dynamic scanning, automated tests) supports continuous ATO. The SSP skeleton, control implementation statements, and incident runbook are already written.
