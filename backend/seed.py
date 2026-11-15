import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path so app can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.knowledge import (
    Fact, FactStatus,
    Guideline,
    Term,
    Rule, RuleType,
    ApprovedAsset,
    SeverityLevel,
)
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.review import (
    Review, ReviewStatus,
    Claim, ClaimStatus,
    Finding, FindingStatus,
    Approval, ApprovalDecision,
)
from app.services.review_orchestrator import ReviewOrchestrator
from app.models.audit import AuditEvent


def seed_database():
    """
    Seeds the BrandProof database with the Northstar Cloud demonstration dataset.
    Strictly restricted to non-production environments.
    """
    if os.environ.get("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("CRITICAL: Seeding demo data is strictly prohibited in production environments.")

    print("Starting BrandProof database seeding with comprehensive knowledge dataset...")
    db = SessionLocal()

    try:
        # Check if Northstar Cloud already exists
        existing_org = db.query(Organization).filter(Organization.slug == "northstar-cloud").first()
        if existing_org:
            print("Demo organization 'Northstar Cloud' already exists. Cleaning up existing demo data...")
            db.delete(existing_org)
            db.commit()

        # 1. Create Organization
        org = Organization(
            name="Northstar Cloud",
            slug="northstar-cloud",
            domain="northstarcloud.com",
            is_active=True,
        )
        db.add(org)
        db.flush()
        print(f"Created Organization: {org.name} ({org.id})")

        # 2. Create Users for all 5 Roles
        # Demo password MUST be provided via DEMO_USER_PASSWORD or securely generated in dev/test
        demo_password = os.environ.get("DEMO_USER_PASSWORD")
        if not demo_password:
            import secrets
            demo_password = secrets.token_urlsafe(16)
            print(f"[SECURITY NOTICE] DEMO_USER_PASSWORD not set. Generated ephemeral demo password: {demo_password}")
        else:
            print("[SECURITY NOTICE] Provisioning demo accounts using DEMO_USER_PASSWORD from environment.")

        default_password = hash_password(demo_password)

        admin_user = User(
            organization_id=org.id,
            email="admin@northstarcloud.com",
            hashed_password=default_password,
            full_name="Alexandra Vance",
            role=UserRole.ADMIN.value,
            title="VP of Governance & Trust",
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        )
        brand_mgr = User(
            organization_id=org.id,
            email="brandmanager@northstarcloud.com",
            hashed_password=default_password,
            full_name="Marcus Sterling",
            role=UserRole.BRAND_MANAGER.value,
            title="Global Brand Director",
            avatar_url="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        )
        fact_owner = User(
            organization_id=org.id,
            email="factowner@northstarcloud.com",
            hashed_password=default_password,
            full_name="Elena Rostova",
            role=UserRole.FACT_OWNER.value,
            title="Chief Systems Architect",
            avatar_url="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
        )
        reviewer = User(
            organization_id=org.id,
            email="reviewer@northstarcloud.com",
            hashed_password=default_password,
            full_name="Julian Chen",
            role=UserRole.REVIEWER.value,
            title="Senior Legal & Compliance Counsel",
            avatar_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        )
        creator = User(
            organization_id=org.id,
            email="creator@northstarcloud.com",
            hashed_password=default_password,
            full_name="Samantha Reed",
            role=UserRole.CREATOR.value,
            title="Lead Product Marketing Manager",
            avatar_url="https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
        )

        db.add_all([admin_user, brand_mgr, fact_owner, reviewer, creator])
        db.flush()

        # 3. Create Facts (15 Approved + 3 Expired)
        now = datetime.now(timezone.utc)
        future_year = now + timedelta(days=365)
        future_soon = now + timedelta(days=22)  # Expiring soon for amber badge
        expired_past_45 = now - timedelta(days=45)
        expired_past_180 = now - timedelta(days=180)
        expired_past_15 = now - timedelta(days=15)

        facts = [
            # 1. 50+ integrations
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Northstar Enterprise supports 50+ integrations",
                canonical_value="50+",
                description="Verified pre-built connectors with Salesforce, Snowflake, Datadog, ServiceNow, and AWS.",
                source_reference="Product Integration Directory v2.4 (Legal ref #INT-2026-01)",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=60),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 2. 25% onboarding time reduction
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Northstar reduces average onboarding setup time by 25%",
                canonical_value="25%",
                description="Measured across 420 customer deployments in 2025. Unsubstantiated claims claiming 60% are explicitly disallowed.",
                source_reference="Customer Operations Benchmark Study Q4 2025 §3.2",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=90),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 3. 99.999% SLA
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Northstar Sovereign Cloud 99.999% SLA Uptime",
                canonical_value="99.999%",
                description="Delivers contractually guaranteed 99.999% uptime SLA across all tier-4 multi-region clusters.",
                source_reference="Master Service Agreement, Schedule 3.1 (Approved Legal: 2026-01-10)",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=120),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 4. Failover < 10 mins
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Automated Cross-Region Disaster Recovery Failover Under 10 Minutes",
                canonical_value="< 10 minutes",
                description="Cross-region active-active database replication achieves RTO under 10 minutes and RPO under 30 seconds.",
                source_reference="Infrastructure Reliability Drill Report #IR-2026-02",
                product_scope="Enterprise",
                region_scope="US, EU",
                channel_scope="Sales Deck, Website",
                valid_from=now - timedelta(days=45),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 5. SOC-2 Type II
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="SOC-2 Type II Certified for Security and Availability",
                canonical_value="SOC-2 Type II",
                description="Audited annually by independent accredited third-party auditing partners.",
                source_reference="PwC Annual Compliance Audit Report #SOC-2025-NS89",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=180),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 6. Dedicated HSM
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Zero Trust Dedicated HSM Key Custody",
                canonical_value="Dedicated HSM",
                description="Hardware-accelerated AES-256 encryption at rest and mTLS 1.3 with client-held Dedicated HSM custody.",
                source_reference="Cryptographic Architecture Charter §4.8",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="Security Whitepaper",
                valid_from=now - timedelta(days=30),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 7. Sub-ms latency
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Sub-millisecond Edge API Gateway Latency in North America",
                canonical_value="< 1ms",
                description="Benchmarked across 28 edge points of presence in continental US.",
                source_reference="Edge Network Performance Benchmark 2026",
                product_scope="Pro, Enterprise",
                region_scope="US",
                channel_scope="Website, Advertisement",
                valid_from=now - timedelta(days=60),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 8. GDPR Frankfurt & Dublin
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Full GDPR Data Residency in Frankfurt and Dublin",
                canonical_value="Frankfurt & Dublin",
                description="All European customer data guaranteed to reside strictly within EU sovereignty zones.",
                source_reference="EU Data Sovereignty Legal Memorandum §1.4",
                product_scope="All",
                region_scope="EU",
                channel_scope="Website, Sales Deck",
                valid_from=now - timedelta(days=90),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 9. RBI Compliance India
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Reserve Bank of India (RBI) Payment Data Localization Compliance",
                canonical_value="RBI Compliant",
                description="Compliant with RBI Directive on Storage of Payment System Data within domestic Indian data centers.",
                source_reference="RBI Payment Data Localization Audit Report #RBI-2025-NS",
                product_scope="Enterprise",
                region_scope="India",
                channel_scope="Sales Deck, Email",
                valid_from=now - timedelta(days=75),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 10. Starter tier seats
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Northstar Starter includes 5 automated pipeline seats",
                canonical_value="5 seats",
                description="Standard tier packaging for early-stage teams.",
                source_reference="Commercial Pricing Matrix Schedule A (Approved: 2026-01-01)",
                product_scope="Starter",
                region_scope="Global",
                channel_scope="Website, Email",
                valid_from=now - timedelta(days=40),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 11. Pro tier seats
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Northstar Pro includes 25 active compliance team seats",
                canonical_value="25 seats",
                description="Pro tier packaging for growing growth companies.",
                source_reference="Commercial Pricing Matrix Schedule B (Approved: 2026-01-01)",
                product_scope="Pro",
                region_scope="Global",
                channel_scope="Website, Sales Deck",
                valid_from=now - timedelta(days=40),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 12. Carbon neutral 2028 (Expiring Soon - 22 days left)
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="100% Carbon Neutral Operations Target by 2028 (Scope 1 & 2)",
                canonical_value="2028",
                description="Annual renewable power purchase certification expiring next month; recertification in progress.",
                source_reference="Northstar Sustainability Commitment & Climate Charter 2025",
                product_scope="All",
                region_scope="Global",
                channel_scope="Social, Press",
                valid_from=now - timedelta(days=340),
                expires_at=future_soon,  # < 30 days -> Amber indicator
                status=FactStatus.APPROVED.value,
            ),
            # 13. SSO Federated
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Federated Single Sign-On (SAML 2.0 & OIDC) included on Enterprise tier",
                canonical_value="SAML 2.0 & OIDC",
                description="Enterprise authentication integration supporting Okta, Azure AD, and PingIdentity.",
                source_reference="Identity & Access Integration Guide v3.1",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=100),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 14. HIPAA BAA
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="HIPAA Business Associate Agreement (BAA) Availability",
                canonical_value="HIPAA BAA Available",
                description="Enables US healthcare entities to process protected health information legally.",
                source_reference="Healthcare Compliance Framework Ref #HIPAA-2025",
                product_scope="Enterprise",
                region_scope="US",
                channel_scope="Sales Deck, Website",
                valid_from=now - timedelta(days=110),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),
            # 15. 1.2M claims verified daily
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="Over 1.2 million claims verified daily across global tenants",
                canonical_value="1.2M+",
                description="Production pipeline governance throughput metric.",
                source_reference="Q4 2025 Production Metrics Dashboard (Telemetry ref #TEL-2025-Q4)",
                product_scope="All",
                region_scope="Global",
                channel_scope="Social, Advertisement",
                valid_from=now - timedelta(days=50),
                expires_at=future_year,
                status=FactStatus.APPROVED.value,
            ),

            # EXPIRED FACTS (To demonstrate stale-fact detection & red status indicators)
            # 16. ISO 27001 certified (Expired 45 days ago)
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="ISO 27001 certified",
                canonical_value="ISO/IEC 27001:2013",
                description="Former ISO certification expired on 2026-09-30. Recertification audit is currently underway.",
                source_reference="BSI Certificate #IS-99210 (Expired Oct 2025)",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=400),
                expires_at=expired_past_45,  # EXPIRED DATE
                status=FactStatus.EXPIRED.value,
            ),
            # 17. SOC-2 Type I Audit 2023 (Expired 180 days ago)
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="SOC-2 Type I Point-in-Time Audit 2023",
                canonical_value="SOC-2 Type I (Historical)",
                description="Historical audit superseded by ongoing Type II continuous audits.",
                source_reference="Historical Audit Report #2023-01",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                valid_from=now - timedelta(days=500),
                expires_at=expired_past_180,  # EXPIRED DATE
                status=FactStatus.EXPIRED.value,
            ),
            # 18. FY2024 Renewable Energy Matching Guarantee (Expired 15 days ago)
            Fact(
                organization_id=org.id,
                owner_id=fact_owner.id,
                title="FY2024 Renewable Energy Matching Guarantee",
                canonical_value="100% FY2024 Matching",
                description="FY2024 certificate expired. Must not be used for 2026 marketing releases until FY2025 renewal is finalized.",
                source_reference="Clean Energy Council Certificate 2024-CEC-99",
                product_scope="All",
                region_scope="Global",
                channel_scope="Marketing, Press",
                valid_from=now - timedelta(days=380),
                expires_at=expired_past_15,  # EXPIRED DATE
                status=FactStatus.EXPIRED.value,
            ),
        ]
        db.add_all(facts)
        db.flush()
        print(f"Created {len(facts)} Facts (15 Approved + 3 Expired).")

        # 4. Create Guidelines (8 total across requested categories)
        guidelines = [
            Guideline(
                organization_id=org.id,
                title="Unsubstantiated Superiority and Superlative Claims",
                description="Never use unqualified superlatives such as 'the world's most secure cloud' or 'unbreakable protection' without an explicit, verifiable third-party industry benchmark cited in the same paragraph.",
                principle="Unqualified superlative and superiority claims are prohibited without documented evidence.",
                do_examples=["Evaluated against industry benchmarks", "Designed with audited defense-in-depth architecture"],
                dont_examples=["the #1 onboarding solution", "world's most impenetrable", "unbreakable protection"],
                category="Claims",
                severity=SeverityLevel.BLOCKER.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                source_reference="FTC Advertising Substantiation Principles & Legal Governance §2.1",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="Forward-Looking ESG & Carbon Milestones",
                description="Claims regarding carbon neutrality or net-zero milestones must explicitly specify the target year, the scope (Scope 1, 2, or 3), and link to the latest audited ESG disclosures.",
                principle="Environmental claims must include scope and audited validation date.",
                do_examples=["Targeting Scope 1 and 2 carbon neutrality by 2030 (audited ESG report)"],
                dont_examples=["100% green without caveats", "zero carbon impact today"],
                category="Legal",
                severity=SeverityLevel.HIGH.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="Website, Social",
                source_reference="EU Green Claims Directive & Northstar ESG Policy §7",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="Authoritative & Mathematically Precise Brand Voice",
                description="Brand voice must be authoritative, mathematically precise, humble, and forward-looking. Avoid colloquial hyperbole, sensationalism, and derogatory references to competitors.",
                principle="Speak with rigorous precision and humble authority, avoiding promotional exaggeration.",
                do_examples=["Northstar delivers 99.95% measured SLA availability across all regions", "Our automated data migration framework reduces cutover time by 25%"],
                dont_examples=["miraculous results", "insanely fast", "cheap as dirt", "immediate productivity improvements"],
                category="Brand Voice",
                severity=SeverityLevel.WARNING.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                source_reference="Northstar Brand Identity System v3.0, pg 14-18",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="Autonomous AI Capabilities and Human Oversight",
                description="Autonomous AI capabilities must always state human oversight safeguards. Never claim 'zero error rate' or '100% hallucinations-free'.",
                category="Product",
                severity=SeverityLevel.BLOCKER.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                source_reference="Responsible AI Architecture Charter 2026",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="Web Content Accessibility Guidelines (WCAG) Alt Text",
                description="All public web and social drafts referencing charts, architectural diagrams, or infographic figures must specify descriptive alternative text for screen readers.",
                category="Accessibility",
                severity=SeverityLevel.WARNING.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="Website, Social",
                source_reference="WCAG 2.1 AA Compliance Standard §1.1.1",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="High Contrast Visual Hierarchy in Collateral",
                description="Maintain at least 4.5:1 text-to-background contrast ratio across all brand documentation and sales decks.",
                category="Visual",
                severity=SeverityLevel.INFO.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="Sales Deck, Website",
                source_reference="Brand Design System Guide v2.4",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="European Union VAT Disclosure Requirements",
                description="All pricing claims distributed in EU regions must clarify whether pricing is inclusive or exclusive of Value Added Tax (VAT).",
                category="Regional",
                severity=SeverityLevel.HIGH.value,
                product_scope="All",
                region_scope="EU",
                channel_scope="Website, Advertisement",
                source_reference="EU Consumer Rights Directive 2011/83/EU §6",
                status="Approved",
                active=True,
            ),
            Guideline(
                organization_id=org.id,
                title="Beta and Preview Feature Disclaimers",
                description="Unreleased and private beta features must never be marketed as production ready without standard experimental preview disclosures.",
                category="Product",
                severity=SeverityLevel.BLOCKER.value,
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                source_reference="Product Management Lifecycle Framework §4.2",
                status="Approved",
                active=True,
            ),
        ]
        db.add_all(guidelines)
        db.flush()
        print(f"Created {len(guidelines)} Brand Guidelines.")

        # 5. Create Terminology (10 entries)
        terms = [
            Term(
                organization_id=org.id,
                approved_term="Northstar Pro",
                disallowed_variants=["Northstar Premium", "Northstar Plus", "NS Pro"],
                replacement="Northstar Pro",
                notes="Official tier 2 product brand name. Never use 'Premium' or 'Plus'.",
                product_scope="Pro",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Northstar Sovereign Cloud",
                disallowed_variants=["Northstar v1", "Northstar Cloud Enterprise", "Northstar Sovereign", "NS Sovereign"],
                replacement="Northstar Sovereign Cloud",
                notes="Official tier-1 enterprise brand name. Must not be truncated in marketing copy.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="CloudShield Intelligence",
                disallowed_variants=["Shield", "CloudShield AI", "Northstar Shield", "Cloud Shield"],
                replacement="CloudShield Intelligence",
                notes="Registered trademarked enterprise security suite.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Live Zero-Downtime Migration",
                disallowed_variants=["Instant Migration", "Zero-effort switch", "Automatic 1-click cloud port"],
                replacement="Live Zero-Downtime Migration",
                notes="Engineering precision standard for migration descriptions.",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="BrandProof Pre-Publication Governance",
                disallowed_variants=["BrandProof Scanner", "Brand checker", "Brand AI bot", "Brand checker tool"],
                replacement="BrandProof Pre-Publication Governance",
                notes="Position as serious governance infrastructure, not a simple linting bot.",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Tier-4 Hyperscale Clusters",
                disallowed_variants=["Tier 5 Data Center", "Ultra-scale data centers", "Bulletproof servers"],
                replacement="Tier-4 Hyperscale Clusters",
                notes="Adhere to standard Uptime Institute data center tier terminology.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Dedicated HSM Key Custody",
                disallowed_variants=["Private key manager", "Hardware lock", "Secret safe"],
                replacement="Dedicated HSM Key Custody",
                notes="Precise cryptographic specification term.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="Security Whitepaper",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Northstar Starter",
                disallowed_variants=["Northstar Free", "Northstar Lite", "Starter Pack"],
                replacement="Northstar Starter",
                notes="Official entry-tier product branding.",
                product_scope="Starter",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Northstar Enterprise",
                disallowed_variants=["Enterprise Tier", "Northstar Big Business", "NS Enterprise"],
                replacement="Northstar Enterprise",
                notes="Tier 3 enterprise branding.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Term(
                organization_id=org.id,
                approved_term="Active-Active Disaster Recovery",
                disallowed_variants=["Instant disaster backup", "Hot failover clone", "Miracle recovery"],
                replacement="Active-Active Disaster Recovery",
                notes="Accurate engineering terminology for multi-region clustering.",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
        ]
        db.add_all(terms)
        db.flush()
        print(f"Created {len(terms)} Brand Terminology entries.")

        # 6. Create Rules (8 deterministic rule types)
        rules = [
            Rule(
                organization_id=org.id,
                name="Brand Naming Policy - Northstar Pro",
                description="Detects disallowed variant product names such as 'Northstar Premium' and 'Northstar Plus' and enforces 'Northstar Pro'.",
                rule_type=RuleType.TERM_CHECK.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "target_term": "Northstar Pro",
                    "forbidden_variants": ["Northstar Premium", "Northstar Plus", "NS Pro"]
                },
                source_reference="Brand Identity Dictionary Ref #TERM-PRO-01",
                product_scope="Pro",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="Mandatory SLA Disclaimer Footnote",
                description="Any public or sales publication mentioning 99.999% uptime SLA must include the mandatory footnote: 'Subject to terms of the Northstar Enterprise SLA Agreement'.",
                rule_type=RuleType.REQUIRED_DISCLAIMER.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "required_disclaimer": "Subject to terms of the Northstar Enterprise SLA Agreement",
                    "trigger_keywords": ["99.999%", "five nines", "uptime SLA"]
                },
                source_reference="Legal Standard Terms Ref #DISC-SLA-01",
                product_scope="Enterprise",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="Unsubstantiated Superlative Filter",
                description="Flags marketing claims asserting 'world's most', 'unbreakable', '100% guarantee' without verified third-party evidence.",
                rule_type=RuleType.FORBIDDEN_PHRASE.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "forbidden_phrases": ["world's most", "unbreakable protection", "100% hack-proof", "guaranteed zero risk"]
                },
                source_reference="FTC Advertising Substantiation Rules §2.1",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="Onboarding Setup Metric Exact Value Check",
                description="Verifies that onboarding efficiency claims cite the verified benchmark figure of '25%'. Explicitly flags exaggerated claims such as '60%'.",
                rule_type=RuleType.EXACT_VALUE.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "approved_metric": "25%",
                    "disallowed_exaggerations": ["60%", "75%", "50%"],
                    "metric_context": "onboarding setup time"
                },
                source_reference="Customer Operations Benchmark Study Q4 2025 §3.2",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="Stale Fact & Expired Certification Check",
                description="Automatically flags citations of expired certifications (e.g., ISO 27001:2013) that have expired.",
                rule_type=RuleType.EXPIRY_CHECK.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "expired_fact_triggers": ["ISO 27001 certified", "ISO/IEC 27001:2013", "FY2024 Renewable Energy"]
                },
                source_reference="Compliance Certifications Registry 2026",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="SOC-2 Audit Period Specification Check",
                description="Requires that any SOC-2 mention must explicitly state 'Type II' and reference ongoing audit periods.",
                rule_type=RuleType.REGEX.value,
                severity=SeverityLevel.HIGH.value,
                configuration={
                    "pattern": r"SOC[\s-]?2\s+(?!Type\s+II)",
                    "message": "SOC-2 mentions must specify 'Type II' auditing."
                },
                source_reference="Compliance Standards Ref #AUDIT-SOC-04",
                product_scope="All",
                region_scope="Global",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="Image Accessibility Alt-Text Rule",
                description="Ensures markdown image inclusions include non-empty descriptive alt-text tags.",
                rule_type=RuleType.ACCESSIBILITY.value,
                severity=SeverityLevel.WARNING.value,
                configuration={
                    "require_alt_text": True
                },
                source_reference="WCAG 2.1 AA §1.1.1",
                product_scope="All",
                region_scope="Global",
                channel_scope="Website, Social",
                status="Approved",
                active=True,
            ),
            Rule(
                organization_id=org.id,
                name="European Data Sovereignty Regional Policy",
                description="Ensures all European marketing drafts state data residency in Frankfurt or Dublin data centers.",
                rule_type=RuleType.CUSTOM.value,
                severity=SeverityLevel.BLOCKER.value,
                configuration={
                    "region": "EU",
                    "required_locations": ["Frankfurt", "Dublin"]
                },
                source_reference="EU Data Sovereignty Legal Memorandum §1.4",
                product_scope="All",
                region_scope="EU",
                channel_scope="All",
                status="Approved",
                active=True,
            ),
        ]
        db.add_all(rules)
        db.flush()
        print(f"Created {len(rules)} Governance Rules.")

        # 6b. Create Approved Brand Assets
        logo_asset = ApprovedAsset(
            organization_id=org.id,
            name="Northstar Primary Horizontal Lockup",
            asset_type="logo",
            file_path="/assets/branding/northstar_logo_primary.svg",
            expected_width=400.0,
            expected_height=100.0,
            aspect_ratio=4.0,
            allowed_ratio_deviation=0.05,
            source_reference="Brand Identity Guidelines v2.4 §4.1 Logo Proportions",
            product_scope="All",
            region_scope="Global",
            channel_scope="All",
            status="Approved",
            active=True,
        )
        badge_asset = ApprovedAsset(
            organization_id=org.id,
            name="ISO 27001 Official Certification Badge",
            asset_type="badge",
            file_path="/assets/branding/iso27001_badge.png",
            expected_width=200.0,
            expected_height=200.0,
            aspect_ratio=1.0,
            allowed_ratio_deviation=0.02,
            source_reference="BSI Certification Trademark Guidelines 2025",
            product_scope="Enterprise",
            region_scope="Global",
            channel_scope="Website, Whitepaper",
            status="Approved",
            active=True,
        )
        db.add_all([logo_asset, badge_asset])
        db.flush()
        print("Created Approved Brand Assets.")

        # 7. Create Demo Documents & Initial Reviews
        sample_doc_content = """# Northstar Sovereign Cloud Launch Memo

Northstar Sovereign Cloud delivers a 99.999% SLA uptime guarantee for regulated banking and healthcare.

Northstar Pro provides teams with 25 compliance seats. We reduce average onboarding setup time by 25%.

We are recognized as the world's most impenetrable cloud platform. Audited under ISO 27001 certified and SOC-2 Type II standards.
"""

        doc1 = Document(
            organization_id=org.id,
            creator_id=creator.id,
            title="Q1 Sovereign Cloud Launch Memo",
            filename="sovereign_launch_memo.md",
            file_type="text/markdown",
            file_path="sovereign_launch_memo.md",
            file_size=len(sample_doc_content.encode("utf-8")),
            product="Enterprise",
            region="Global",
            channel="Website & PR",
            status=DocumentStatus.NEEDS_REVIEW.value,
        )
        db.add(doc1)
        db.flush()

        ver1 = DocumentVersion(
            document_id=doc1.id,
            created_by_id=creator.id,
            version_number=1,
            file_path="sovereign_launch_memo.md",
            file_size=doc1.file_size,
            extracted_text=sample_doc_content,
        )
        db.add(ver1)
        db.flush()

        review1 = Review(
            organization_id=org.id,
            document_id=doc1.id,
            version_id=ver1.id,
            reviewer_id=reviewer.id,
            status=ReviewStatus.NEEDS_REVIEW.value,
            summary="Pre-publication audit checking SLA footnote disclaimers, onboarding metric veracity, and expired ISO certification.",
        )
        db.add(review1)
        db.flush()

        # Claims
        c1 = Claim(
            review_id=review1.id,
            document_id=doc1.id,
            text="Northstar Sovereign Cloud delivers a 99.999% SLA uptime guarantee.",
            location_metadata={"line": 3},
            confidence=0.98,
            status=ClaimStatus.PROPOSED.value,
        )
        c2 = Claim(
            review_id=review1.id,
            document_id=doc1.id,
            text="We reduce average onboarding setup time by 25%.",
            location_metadata={"line": 5},
            confidence=0.99,
            status=ClaimStatus.VERIFIED.value,
        )
        c3 = Claim(
            review_id=review1.id,
            document_id=doc1.id,
            text="We are recognized as the world's most impenetrable cloud platform.",
            location_metadata={"line": 7},
            confidence=0.99,
            status=ClaimStatus.DISPUTED.value,
        )
        c4 = Claim(
            review_id=review1.id,
            document_id=doc1.id,
            text="Audited under ISO 27001 certified standards.",
            location_metadata={"line": 7},
            confidence=0.95,
            status=ClaimStatus.UNVERIFIED.value,
        )
        db.add_all([c1, c2, c3, c4])
        db.flush()

        # Findings strictly referenced
        f1 = Finding(
            review_id=review1.id,
            claim_id=c1.id,
            rule_id=rules[1].id,
            fact_id=facts[2].id,
            severity=SeverityLevel.BLOCKER.value,
            message="Uptime SLA claim is missing mandatory legal footnote disclaimer.",
            suggestion="Append footnote: 'Subject to terms of the Northstar Enterprise SLA Agreement'.",
            status=FindingStatus.OPEN.value,
            source_reference=rules[1].source_reference,
        )
        f2 = Finding(
            review_id=review1.id,
            claim_id=c3.id,
            guideline_id=guidelines[0].id,
            severity=SeverityLevel.BLOCKER.value,
            message="Unqualified superlative 'world's most impenetrable' violates advertising substantiation rules.",
            suggestion="Remove superlative assertion or cite specific accredited third-party benchmark.",
            status=FindingStatus.OPEN.value,
            source_reference=guidelines[0].source_reference,
        )
        f3 = Finding(
            review_id=review1.id,
            claim_id=c4.id,
            fact_id=facts[15].id,
            rule_id=rules[4].id,
            severity=SeverityLevel.BLOCKER.value,
            message="STALE FACT DETECTED: 'ISO 27001 certified' expired 45 days ago. Recertification is pending.",
            suggestion="Remove citation of expired ISO certificate until BSI recertification audit report is registered.",
            status=FindingStatus.OPEN.value,
            source_reference=facts[15].source_reference,
        )
        db.add_all([f1, f2, f3])
        db.flush()

        # 7b. Seed specific Marketing Draft requested by BrandProof prompt
        # "Northstar Premium cuts employee onboarding time by 60%. Our ISO 27001 certified platform is the #1 onboarding solution and guarantees immediate productivity improvements."
        # Contrived with multiple issues for future checking engines:
        # - "Northstar Premium" instead of approved "Northstar Pro"
        # - 60% claim conflicting with approved 25%
        # - expired ISO certification
        # - "#1" unsupported claim
        # - "guarantees" risky language
        marketing_draft_text = (
            "# Q2 Onboarding Acceleration Campaign Draft\n\n"
            "Northstar Premium cuts employee onboarding time by 60%. "
            "Our ISO 27001 certified platform is the #1 onboarding solution "
            "and guarantees immediate productivity improvements.\n\n"
            "Scale your distributed enterprise teams with zero manual friction."
        )
        orchestrator = ReviewOrchestrator(db)
        marketing_review, marketing_doc, marketing_ver = orchestrator.ingest_pasted_text(
            text_content=marketing_draft_text,
            title="Q2 Onboarding Acceleration Ad Copy",
            creator_id=creator.id,
            organization_id=org.id,
            intent_card={
                "title": "Q2 Onboarding Acceleration Ad Copy",
                "product": "Northstar Pro",
                "region": "India",
                "channel": "Advertisement",
                "content_type": "Ad Copy",
                "intended_audience": "Enterprise IT leaders",
                "purpose": "Promote faster employee onboarding",
            },
        )

        # 8. Initial Audit Trail
        audit1 = AuditEvent(
            organization_id=org.id,
            actor_id=admin_user.id,
            action="ORGANIZATION_INITIALIZED",
            entity_type="Organization",
            entity_id=org.id,
            event_metadata={"name": org.name, "domain": org.domain},
            timestamp=now - timedelta(days=60),
        )
        audit2 = AuditEvent(
            organization_id=org.id,
            actor_id=fact_owner.id,
            action="FACT_CREATED",
            entity_type="Fact",
            entity_id=facts[0].id,
            event_metadata={"title": facts[0].title, "source": facts[0].source_reference},
            timestamp=now - timedelta(days=60),
        )
        audit3 = AuditEvent(
            organization_id=org.id,
            actor_id=fact_owner.id,
            action="FACT_EXPIRED",
            entity_type="Fact",
            entity_id=facts[15].id,
            event_metadata={"title": facts[15].title, "expired_at": str(facts[15].expires_at)},
            timestamp=now - timedelta(days=45),
        )
        audit4 = AuditEvent(
            organization_id=org.id,
            actor_id=brand_mgr.id,
            action="TERM_CREATED",
            entity_type="Term",
            entity_id=terms[0].id,
            event_metadata={"term": terms[0].approved_term, "disallowed": terms[0].disallowed_variants},
            timestamp=now - timedelta(days=30),
        )
        audit5 = AuditEvent(
            organization_id=org.id,
            actor_id=brand_mgr.id,
            action="RULE_CREATED",
            entity_type="Rule",
            entity_id=rules[0].id,
            event_metadata={"name": rules[0].name, "rule_type": rules[0].rule_type},
            timestamp=now - timedelta(days=30),
        )
        db.add_all([audit1, audit2, audit3, audit4, audit5])

        db.commit()
        print("Northstar Cloud successfully seeded with complete expanded Knowledge Base!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
