"""
scripts/seed_knowledge.py
--------------------------
Populate the Qdrant knowledge base with:
  1. RERA Law 33 / Law 26 regulations (key articles)
  2. Company lease policies (maintenance, move-in/out, renewal)
  3. Tenant FAQ

Run once after Qdrant is up and the collection is created:
    python -m scripts.seed_knowledge

Re-running is idempotent — each document has a stable point_id
so Qdrant upserts rather than duplicates.
"""

import asyncio
import os
import sys

# Allow running from the project root: python -m scripts.seed_knowledge
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.vector.qdrant_client import QdrantService


# ══════════════════════════════════════════════════════════════════════════
# KNOWLEDGE DOCUMENTS
# Each dict: text, source, doc_type, point_id (stable UUID), metadata
# ══════════════════════════════════════════════════════════════════════════

DOCUMENTS: list[dict] = [

    # ─────────────────────────────────────────────────────────────────────
    # SECTION 1 — RERA Law 33 (Tenancy Relations in Dubai)
    # ─────────────────────────────────────────────────────────────────────

    {
        "point_id": "rera-law33-article1",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Law No. 33 of 2008 governs all tenancy relations in the Emirate of Dubai. "
            "It applies to all rental agreements for residential and commercial properties, "
            "whether signed before or after the law came into effect. "
            "The law is administered by the Real Estate Regulatory Agency (RERA), "
            "a division of the Dubai Land Department (DLD)."
        ),
        "metadata": {"article": "Overview", "law": "Law 33/2008"},
    },
    {
        "point_id": "rera-law33-notice-nonrenewal",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Law 33, Article 25: If a landlord does not wish to renew a tenancy contract, "
            "they must notify the tenant at least 90 days before the lease expiry date. "
            "This notice must be in writing and served through a notary public or registered mail. "
            "If the 90-day notice is not given, the landlord cannot refuse renewal on grounds "
            "of non-renewal. Failure to notify within 90 days typically results in automatic "
            "renewal of the lease under the same terms for an equivalent period."
        ),
        "metadata": {"article": "25", "law": "Law 33/2008", "topic": "non-renewal notice"},
    },
    {
        "point_id": "rera-law33-rent-increase",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Rent Increase Calculator (based on Decree No. 43 of 2013): "
            "Rent increases during renewal are capped based on how far the current rent is "
            "below the RERA average market rent for similar units in the same area: "
            "- If current rent is up to 10% below market rate: no increase permitted. "
            "- If current rent is 11%–20% below market rate: maximum 5% increase. "
            "- If current rent is 21%–30% below market rate: maximum 10% increase. "
            "- If current rent is 31%–40% below market rate: maximum 15% increase. "
            "- If current rent is more than 40% below market rate: maximum 20% increase. "
            "Landlords and tenants can check the current RERA rental index on the Dubai REST app "
            "or the DLD website to verify market rates."
        ),
        "metadata": {"article": "Decree 43/2013", "law": "Law 33/2008", "topic": "rent increase"},
    },
    {
        "point_id": "rera-law33-tenant-eviction",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Law 33, Article 25: A landlord may request eviction of a tenant only in "
            "specific circumstances, including: "
            "(a) The tenant has not paid rent within 30 days of a registered notice to pay. "
            "(b) The tenant has subleased the property without the landlord's written consent. "
            "(c) The property is being used for illegal or immoral purposes. "
            "(d) The property requires demolition or major renovation as approved by competent authorities. "
            "(e) The landlord intends to sell the property. "
            "(f) The landlord or a first-degree relative needs the property for personal use "
            "(12 months' notice required). "
            "All eviction notices must go through a notary public or registered mail."
        ),
        "metadata": {"article": "25", "law": "Law 33/2008", "topic": "eviction grounds"},
    },
    {
        "point_id": "rera-law33-ejari",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "Ejari (meaning 'My Rent' in Arabic) is the mandatory tenancy contract registration "
            "system operated by the Dubai Land Department (DLD). "
            "All tenancy contracts in Dubai must be registered with Ejari within 30 days of signing. "
            "The Ejari certificate is required to: connect DEWA (water and electricity), "
            "apply for residency visas, renew trade licenses, and for any legal dispute proceedings. "
            "Registration can be done online via the Ejari system, the Dubai REST app, or "
            "through authorised typing centres. "
            "The Ejari registration fee is typically borne by the tenant unless agreed otherwise."
        ),
        "metadata": {"topic": "ejari", "law": "Law 33/2008"},
    },
    {
        "point_id": "rera-law33-maintenance-landlord",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Law 33, Article 16: The landlord is responsible for maintaining the property "
            "in a condition fit for the agreed purpose of use throughout the tenancy period. "
            "The landlord must carry out all repairs needed to maintain the property unless "
            "the damage is caused by the tenant's misuse or negligence. "
            "Tenants must promptly notify the landlord of any defects or damage. "
            "For urgent repairs (e.g. gas leaks, flooding, structural damage), "
            "the landlord must act within a reasonable timeframe or the tenant may carry out "
            "necessary repairs and deduct the cost from rent after notifying the landlord."
        ),
        "metadata": {"article": "16", "law": "Law 33/2008", "topic": "maintenance obligations"},
    },
    {
        "point_id": "rera-law33-rental-disputes",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "Rental Dispute Settlement Centre (RDSC): All disputes between landlords and tenants "
            "in Dubai must be filed with the Rental Dispute Settlement Centre (RDSC), "
            "located at the Dubai Land Department. "
            "The RDSC handles cases including: unpaid rent, eviction disputes, "
            "rent increase disagreements, maintenance issues, and contract violations. "
            "Filing fee is 3.5% of annual rent (minimum AED 500, maximum AED 15,000). "
            "The RDSC aims to resolve disputes within 30 days for straightforward cases. "
            "Both parties must bring original documents including the tenancy contract, "
            "Ejari certificate, and supporting evidence."
        ),
        "metadata": {"topic": "dispute resolution", "law": "Law 33/2008"},
    },
    {
        "point_id": "rera-law33-tenancy-duration",
        "source": "rera_law_33",
        "doc_type": "regulation",
        "text": (
            "RERA Law 33: Tenancy contracts in Dubai are typically for one year, "
            "though longer or shorter durations are permitted by mutual agreement. "
            "Upon expiry of a fixed-term lease, if neither party gives notice, "
            "the lease is automatically renewed for the same period and under the same terms. "
            "Month-to-month tenancy is less common but legally recognised. "
            "Commercial leases may have different terms negotiated between parties "
            "but are still subject to RERA Law 33 provisions."
        ),
        "metadata": {"topic": "lease duration", "law": "Law 33/2008"},
    },

    # ─────────────────────────────────────────────────────────────────────
    # SECTION 2 — Company Lease Policies
    # ─────────────────────────────────────────────────────────────────────

    {
        "point_id": "policy-lease-creation",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Lease Creation Policy: "
            "A new lease may only be created after all of the following conditions are met: "
            "(1) The unit is in 'available' status in the system. "
            "(2) The tenant has passed identity verification (valid passport, Emirates ID, and visa on file). "
            "(3) The tenant is not on the blacklist. "
            "(4) The tenant has provided a valid UAE residency visa (or a valid visit visa for short-term leases). "
            "Leases are created in DRAFT status. They become ACTIVE only after digital signing by both parties "
            "and Ejari registration within 30 days of signing. "
            "Annual rent is recorded in AED for RERA compliance purposes only — not as a payment instruction."
        ),
        "metadata": {"topic": "lease creation"},
    },
    {
        "point_id": "policy-renewal-process",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Lease Renewal Policy: "
            "The leasing team must initiate renewal discussions at least 90 days before any lease expiry. "
            "The proposed renewal rent must comply with the RERA rent increase calculator. "
            "The renewal offer must be sent in writing (email or registered mail) to the tenant. "
            "Tenants have 15 days to respond to a renewal offer. "
            "If the tenant does not respond within 15 days, the offer lapses and the leasing team "
            "must assess whether to re-issue or proceed with non-renewal notice. "
            "A new Ejari certificate must be obtained for every renewed lease. "
            "All renewals must be recorded in the system as a Renewal record linked to the original lease."
        ),
        "metadata": {"topic": "renewal"},
    },
    {
        "point_id": "policy-maintenance-sla",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Maintenance Request SLA Policy: "
            "All maintenance requests are assigned a Service Level Agreement (SLA) based on priority: "
            "- Emergency (flooding, gas leak, fire risk, total power loss): respond and dispatch within 1 hour. "
            "- High (AC failure in summer, hot water failure, broken locks): resolve within 6 hours. "
            "- Medium (appliance issues, minor plumbing, damaged fixtures): resolve within 48 hours (2 business days). "
            "- Low (cosmetic issues, painting, minor carpentry): resolve within 120 hours (5 business days). "
            "Tenants will receive an SMS/email confirmation when their request is logged, assigned, "
            "and when the work is completed. Tenants are asked to rate the service on a scale of 1–5 "
            "after completion. SLA breaches are escalated to the Property Manager."
        ),
        "metadata": {"topic": "maintenance SLA"},
    },
    {
        "point_id": "policy-move-in",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Move-In Policy: "
            "Before a tenant moves in, the following must be completed: "
            "(1) Lease must be in ACTIVE status (signed by both parties, Ejari registered). "
            "(2) A move-in inspection checklist must be completed by the Leasing Agent and the tenant together. "
            "(3) The checklist documents the condition of all fixtures, appliances, walls, and fittings. "
            "(4) Both parties sign the move-in checklist; a copy is retained in the tenant file. "
            "(5) Keys, access cards, and parking permits are handed over on the first day of the lease. "
            "DEWA connection is the tenant's responsibility; the Ejari certificate is required for this. "
            "The unit is handed over in a clean and functional condition."
        ),
        "metadata": {"topic": "move-in"},
    },
    {
        "point_id": "policy-move-out",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Move-Out and Lease Termination Policy: "
            "Tenants must give written notice of intent to vacate per the notice period in the lease "
            "(default 60 days unless otherwise agreed). "
            "A move-out inspection must be scheduled within 7 days of the tenant's notice. "
            "The Leasing Agent inspects the unit against the original move-in checklist. "
            "Damage beyond fair wear and tear will be documented and reported to the tenant in writing. "
            "Tenants must return all keys, access cards, and parking permits on the last day. "
            "The unit must be vacated in a clean condition. "
            "DEWA must be disconnected by the tenant before handover. "
            "Ejari cancellation is processed within 7 days of lease termination. "
            "The unit status is updated to 'available' after the handover is complete."
        ),
        "metadata": {"topic": "move-out"},
    },
    {
        "point_id": "policy-tenant-screening",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Tenant Screening and KYC Policy: "
            "All prospective tenants must provide the following documents before a lease can be created: "
            "(1) Valid passport (original + copy). "
            "(2) UAE Residency Visa (original + copy) — or a valid visit visa for short-term lets. "
            "(3) Emirates ID (original + copy). "
            "The leasing team checks the tenant against the company blacklist before proceeding. "
            "Documents are checked for authenticity and expiry dates. "
            "Passport expiry must be at least 6 months beyond the lease end date. "
            "Visa expiry must cover the initial lease term or the tenant must provide evidence "
            "of visa renewal in progress. "
            "All documents are stored as LeaseDocument records linked to the tenant profile."
        ),
        "metadata": {"topic": "tenant screening"},
    },
    {
        "point_id": "policy-blacklist",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Tenant Blacklist Policy: "
            "A tenant may be added to the blacklist in the following circumstances: "
            "(1) History of consistently late or unpaid rent. "
            "(2) Deliberate damage to a company property. "
            "(3) Illegal or immoral use of a leased unit. "
            "(4) Abandonment of a unit mid-lease without notice. "
            "(5) Serious or repeated violation of building rules and regulations. "
            "Blacklisting requires approval from the Property Manager. "
            "Blacklisted tenants cannot sign new leases with the company. "
            "A blacklisted tenant may appeal by submitting a written request to the Property Manager "
            "with supporting evidence. Appeals are reviewed within 30 days."
        ),
        "metadata": {"topic": "blacklist"},
    },
    {
        "point_id": "policy-document-management",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Document Management Policy: "
            "All lease-related documents are stored in the system as LeaseDocument records. "
            "Physical originals are scanned and stored in secure cloud storage; only metadata and "
            "storage path references are kept in the database. "
            "Document types include: passport, emirates_id, visa, salary_proof, "
            "tenancy_contract, ejari_certificate, renewal_notice, move_in_checklist, "
            "move_out_checklist, maintenance_invoice, and correspondence. "
            "Document statuses: pending (uploaded, not yet verified), verified, rejected, expired. "
            "Lease Agents must verify documents within 2 business days of upload. "
            "The system flags documents expiring within 30 days for proactive renewal reminders."
        ),
        "metadata": {"topic": "document management"},
    },
    {
        "point_id": "policy-building-rules",
        "source": "company_policy",
        "doc_type": "policy",
        "text": (
            "Building Rules and Tenant Obligations: "
            "All tenants must adhere to the following building rules: "
            "(1) No subletting without written approval from the Property Manager. "
            "(2) No alterations to the unit (painting, drilling, partitioning) without written approval. "
            "(3) Pets are permitted only in designated pet-friendly buildings (check unit details). "
            "(4) Noise must be kept within permitted levels between 10pm and 8am. "
            "(5) Common areas (lifts, lobbies, parking) must not be obstructed. "
            "(6) Waste must be disposed of in designated areas; recycling facilities are available. "
            "(7) Visitors may park in designated visitor parking for a maximum of 4 hours. "
            "Repeat violations result in a formal warning; three warnings may result in lease termination."
        ),
        "metadata": {"topic": "building rules"},
    },

    # ─────────────────────────────────────────────────────────────────────
    # SECTION 3 — Tenant FAQ
    # ─────────────────────────────────────────────────────────────────────

    {
        "point_id": "faq-how-to-register-ejari",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: How do I register my tenancy contract with Ejari? "
            "Answer: Once both you and the landlord have signed the tenancy contract, "
            "it must be registered with Ejari within 30 days. You can register: "
            "(a) Online via the Dubai REST app or the DLD Ejari portal. "
            "(b) In person at an authorised Ejari typing centre. "
            "You will need: the signed tenancy contract, copies of your passport and Emirates ID, "
            "a copy of the landlord's title deed, and the DEWA premises number. "
            "The Ejari certificate is emailed to you once registration is complete. "
            "Keep it safe — you will need it for DEWA connection, visa applications, and more."
        ),
        "metadata": {"topic": "ejari registration"},
    },
    {
        "point_id": "faq-renewal-notice",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: How much notice does my landlord need to give if they don't want to renew my lease? "
            "Answer: Under RERA Law 33, your landlord must give you at least 90 days written notice "
            "before your lease expiry date if they do not intend to renew your contract. "
            "The notice must be sent via a notary public or registered mail. "
            "If they fail to give 90 days notice, they cannot refuse renewal on that basis, "
            "and your lease typically continues under the same terms. "
            "If you have received a non-renewal notice and believe it is unjust, "
            "you can file a case with the Rental Dispute Settlement Centre (RDSC)."
        ),
        "metadata": {"topic": "renewal notice"},
    },
    {
        "point_id": "faq-rent-increase-limit",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: Can my landlord increase my rent at renewal, and by how much? "
            "Answer: Yes, but rent increases are strictly regulated by RERA Decree No. 43 of 2013. "
            "The maximum increase depends on how far your current rent is below the RERA market index "
            "for similar units in your area: "
            "- Up to 10% below market: no increase allowed. "
            "- 11–20% below market: max 5% increase. "
            "- 21–30% below market: max 10% increase. "
            "- 31–40% below market: max 15% increase. "
            "- More than 40% below market: max 20% increase. "
            "You can check the RERA rental index on the Dubai REST app or DLD website. "
            "If your landlord proposes an increase above the allowed cap, you can dispute it "
            "at the Rental Dispute Settlement Centre."
        ),
        "metadata": {"topic": "rent increase"},
    },
    {
        "point_id": "faq-maintenance-emergency",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: What should I do if there is an emergency maintenance issue in my unit? "
            "Answer: For emergencies such as flooding, gas leaks, fire risk, or total power loss, "
            "contact us immediately via the emergency maintenance line. "
            "Our team is required to respond and dispatch a technician within 1 hour. "
            "In the meantime: "
            "- Gas leak: do not switch any lights on or off; open windows and leave the unit. Call Etisalat Gas on 04-8061313. "
            "- Flooding: turn off the main water stopcock if accessible. "
            "- Fire: call 997 (Dubai Civil Defence) immediately. "
            "- Power loss: check your fuse box first; if the building has a power outage, contact DEWA on 04-601-9999. "
            "After the emergency is resolved, log a maintenance request in the system for formal tracking."
        ),
        "metadata": {"topic": "emergency maintenance"},
    },
    {
        "point_id": "faq-subletting",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: Can I sublet my unit or rent it out on Airbnb? "
            "Answer: Subletting any part of your unit without the written approval of the Property Manager "
            "is a violation of your tenancy agreement and RERA Law 33. "
            "Short-term holiday rentals (e.g. Airbnb) require a separate holiday homes permit issued "
            "by the Dubai Tourism and Commerce Marketing (DTCM) department. "
            "Operating without this permit is illegal in Dubai. "
            "If you wish to sublet or rent on a short-term basis, please submit a written request to "
            "the Property Manager. Unauthorised subletting may result in lease termination."
        ),
        "metadata": {"topic": "subletting"},
    },
    {
        "point_id": "faq-move-out-notice",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: How much notice do I need to give if I want to move out? "
            "Answer: Your tenancy contract specifies the required notice period — typically 60 days "
            "for residential leases with this company. "
            "You must provide written notice (email is acceptable) to the Leasing Agent. "
            "On receiving your notice, we will schedule a move-out inspection within 7 days. "
            "The inspection compares the unit's condition to the move-in checklist. "
            "You are responsible for the unit in its original condition, fair wear and tear excepted. "
            "Please ensure DEWA is disconnected in your name and all keys and access cards are returned "
            "on your last day. We will process the Ejari cancellation on your behalf within 7 days."
        ),
        "metadata": {"topic": "move-out notice"},
    },
    {
        "point_id": "faq-lease-status-draft",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: My lease shows 'DRAFT' status — what does that mean? "
            "Answer: A DRAFT lease means the tenancy agreement has been created in the system "
            "but has not yet been signed by both parties. "
            "Next steps to activate your lease: "
            "(1) Review the lease contract document sent to you by the Leasing Agent. "
            "(2) Sign the contract digitally via the signing platform link in your email. "
            "(3) The Leasing Agent will countersign on behalf of the company. "
            "(4) Once both parties have signed, the lease is registered with Ejari. "
            "(5) After Ejari registration, your lease status changes to ACTIVE. "
            "Until the lease is ACTIVE, the unit is reserved for you but cannot be occupied."
        ),
        "metadata": {"topic": "lease status"},
    },
    {
        "point_id": "faq-pets",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: Are pets allowed in my unit? "
            "Answer: Pets are permitted only in buildings that are designated as pet-friendly. "
            "Please check your unit details or ask your Leasing Agent whether your building allows pets. "
            "If your building is pet-friendly, you must: "
            "(1) Notify the Property Manager in writing that you have a pet. "
            "(2) Ensure your pet does not cause damage or disturbance to neighbours. "
            "(3) Clean up after your pet in all common areas. "
            "Damage caused by pets is not considered fair wear and tear and will be charged to the tenant. "
            "Certain pets (e.g. exotic animals, large breeds restricted under Dubai municipality rules) "
            "may require special permits — check with Dubai Municipality."
        ),
        "metadata": {"topic": "pets"},
    },
    {
        "point_id": "faq-lease-renewal-what-happens",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: What happens when my lease expires — does it renew automatically? "
            "Answer: Under RERA Law 33, if neither party gives the required notice before lease expiry, "
            "the lease automatically renews for the same period under the same terms. "
            "However, we recommend proactively renewing your lease rather than relying on automatic renewal. "
            "Our leasing team will contact you at least 90 days before your lease ends to discuss renewal. "
            "If you wish to renew, we will prepare a renewal offer with any applicable rent adjustment "
            "(subject to the RERA rental increase calculator). "
            "Once you accept, a new Ejari certificate is issued for the renewed term."
        ),
        "metadata": {"topic": "lease renewal"},
    },
    {
        "point_id": "faq-maintenance-response-time",
        "source": "faq",
        "doc_type": "faq",
        "text": (
            "FAQ: How long will it take for my maintenance request to be resolved? "
            "Answer: Our response times depend on the priority of your request: "
            "- Emergency (flooding, gas leak, fire risk, power outage): 1 hour response time. "
            "- High priority (AC failure, hot water failure, broken door locks): resolved within 6 hours. "
            "- Medium priority (appliance fault, minor leak, damaged fixture): resolved within 2 business days. "
            "- Low priority (cosmetic issues, painting, non-urgent carpentry): resolved within 5 business days. "
            "You will receive an SMS and email when your request is logged, when a technician is assigned, "
            "and when the job is completed. After completion, please rate our service in the system. "
            "If your request is not resolved within the SLA, please escalate to your Leasing Agent."
        ),
        "metadata": {"topic": "maintenance response time"},
    },
]


# ══════════════════════════════════════════════════════════════════════════
# SEEDER
# ══════════════════════════════════════════════════════════════════════════

async def seed() -> None:
    print(f"Seeding {len(DOCUMENTS)} documents into Qdrant knowledge base...")
    qdrant = QdrantService()

    try:
        await qdrant.ensure_collection()
        print("Collection ready.")

        success = 0
        for i, doc in enumerate(DOCUMENTS, 1):
            try:
                await qdrant.index_document(
                    text=doc["text"],
                    source=doc["source"],
                    doc_type=doc["doc_type"],
                    metadata=doc.get("metadata"),
                    point_id=doc["point_id"],
                )
                print(f"  [{i:02d}/{len(DOCUMENTS)}] OK  {doc['point_id']}")
                success += 1
            except Exception as exc:
                print(f"  [{i:02d}/{len(DOCUMENTS)}] ERR {doc['point_id']}: {exc}")

        print(f"\nDone. {success}/{len(DOCUMENTS)} documents indexed.")
    finally:
        await qdrant.close()


if __name__ == "__main__":
    # Load .env so settings resolve without a running FastAPI app
    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(seed())
