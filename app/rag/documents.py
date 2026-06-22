"""
app/rag/documents.py
---------------------
Structured knowledge base for the Lease Manager Agent.

Five knowledge sources (each a list of document dicts):
  1. lease_policies       — Lease creation, activation, termination, document requirements
  2. tenant_faq           — Common tenant questions and answers
  3. move_in_guidelines   — Pre-move-in checklist, key handover, DEWA, building rules
  4. move_out_guidelines  — Notice period, inspection, handover, Ejari cancellation
  5. renewal_policies     — RERA 90-day rule, rent increase caps, renewal process

Each document dict:
  source    : str   — identifies the knowledge source (used for filtering)
  doc_type  : str   — "policy" | "faq" | "guideline"
  title     : str   — prepended to every chunk for better embedding context
  text      : str   — full document body (chunked by the ingestion pipeline)
  metadata  : dict  — extra payload fields stored in Qdrant (topic, section, etc.)
"""

from typing import Any

# ══════════════════════════════════════════════════════════════════════════════
# 1. LEASE POLICIES
# ══════════════════════════════════════════════════════════════════════════════

LEASE_POLICIES: list[dict[str, Any]] = [
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Lease Eligibility and Pre-Conditions",
        "metadata": {"section": "eligibility"},
        "text": """
A new lease may only be created after all of the following pre-conditions are satisfied:

1. UNIT AVAILABILITY
   The unit must have status "available" in the system. A unit that is "reserved", "occupied",
   or "under_maintenance" cannot be leased until it returns to available status.

2. TENANT IDENTITY VERIFICATION (KYC)
   The prospective tenant must submit valid originals and copies of:
   - Valid passport (must not expire within 6 months of the lease end date)
   - UAE Residency Visa (must cover the full initial lease term, or tenant must show
     evidence of visa renewal in progress)
   - Emirates ID (original and copy)
   Expired documents are not accepted. The Leasing Agent must verify authenticity
   within 2 business days of submission.

3. BLACKLIST CHECK
   The Leasing Agent must confirm the tenant is not on the company blacklist before
   proceeding. Blacklisted tenants cannot sign new leases.

4. SALARY PROOF (OPTIONAL BUT RECOMMENDED)
   For leases above AED 120,000/year, salary slips for the last 3 months or a
   bank statement are strongly recommended.

5. MANAGER APPROVAL (LEASES ABOVE AED 200,000/YEAR)
   Leases with annual rent exceeding AED 200,000 require written approval from
   the Property Manager before the contract is generated.
""".strip(),
    },
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Lease Creation and Draft Status",
        "metadata": {"section": "creation"},
        "text": """
LEASE CREATION PROCESS

Step 1 — Create the Lease Record
  Once all pre-conditions are met, the Leasing Agent creates the lease in the system.
  All new leases are created in DRAFT status.
  The unit is immediately marked as "reserved" to prevent double-booking.

Step 2 — Generate the Tenancy Contract
  The system generates the tenancy contract PDF containing:
  - Property address, unit number, floor
  - Tenant full name, passport number, Emirates ID
  - Lease start date and end date
  - Annual rent amount in AED (in words and numerals)
  - Notice period (default 60 days)
  - Building rules and tenant obligations
  - Ejari registration clause (30-day obligation)

Step 3 — Digital Signing
  The contract is sent to both parties via the digital signing platform.
  The tenant signs first; the company representative countersigns.
  Both signing timestamps are recorded in the system.

Step 4 — Ejari Registration
  After both parties sign, the lease must be registered with Ejari within 30 days.
  Registration is the tenant's responsibility unless agreed otherwise.
  The Ejari number and registration date are recorded in the lease record.

Step 5 — Activation
  Once Ejari registration is complete, the lease status changes to ACTIVE.
  The unit status changes from "reserved" to "occupied".

IMPORTANT: The unit is not handed over to the tenant until the lease is ACTIVE.
""".strip(),
    },
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Lease Termination Policy",
        "metadata": {"section": "termination"},
        "text": """
LEASE TERMINATION POLICY

EARLY TERMINATION BY TENANT
  Tenants wishing to exit before the lease end date must:
  1. Submit a written termination request to the Leasing Agent.
  2. Give notice per the notice period stated in the lease (typically 60 days).
  3. Understand that early termination may incur a financial penalty
     (typically 2 months' rent) — refer to the Finance team for exact amounts.
     NOTE: Financial penalty calculation is handled by the Finance department,
     not the Lease Management system.

TERMINATION BY COMPANY (RERA GROUNDS)
  The company may terminate a lease under RERA Law 33 Article 25 grounds:
  - Non-payment of rent after a registered notice to pay (30-day cure period).
  - Subletting without written consent.
  - Illegal or immoral use of the unit.
  - Persistent violation of building rules after formal warnings.
  All termination notices must be served via registered mail or notary public.

LEASE TERMINATION PROCESS
  1. Issue formal termination notice (registered mail or notary public).
  2. Schedule move-out inspection within 7 days of notice.
  3. Complete inspection against the move-in checklist.
  4. Process key and access card return on vacate date.
  5. Update lease status to TERMINATED in the system.
  6. Update unit status to AVAILABLE after handover is complete.
  7. Cancel Ejari registration within 7 days of termination.

LEASE EXPIRY (NATURAL END)
  If neither party gives notice before the lease expiry date, the lease automatically
  renews under RERA Law 33. If the company intends not to renew, a 90-day written
  notice must be given before the expiry date.
""".strip(),
    },
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Document Requirements and KYC Policy",
        "metadata": {"section": "documents"},
        "text": """
DOCUMENT REQUIREMENTS AND KYC POLICY

REQUIRED DOCUMENTS FOR ALL TENANTS
  The following documents are mandatory before a lease can be created:
  - Passport: valid original, must not expire within 6 months of lease end.
  - UAE Residency Visa: valid, must cover the initial lease term.
  - Emirates ID: valid original and copy.

DOCUMENT VERIFICATION TIMELINE
  Leasing Agents must verify all submitted documents within 2 business days.
  Document statuses in the system:
  - pending   — uploaded by tenant, awaiting agent verification.
  - verified  — agent confirms the document is authentic and valid.
  - rejected  — document is expired, illegible, or suspicious; tenant must resubmit.
  - expired   — a previously verified document has since expired.

DOCUMENT EXPIRY MONITORING
  The system automatically flags documents expiring within 30 days.
  When a tenant's visa or passport is about to expire:
  - Leasing Agent sends a renewal reminder to the tenant.
  - Tenant must provide updated documents within 14 days of expiry.
  - Failure to update documents may result in lease review.

DOCUMENT STORAGE
  Originals are scanned and stored in secure cloud storage.
  Only metadata and the storage path reference are kept in the database.
  Physical originals are returned to the tenant after verification.

DOCUMENT TYPES IN THE SYSTEM
  passport | emirates_id | visa | salary_proof | tenancy_contract |
  ejari_certificate | renewal_notice | move_in_checklist |
  move_out_checklist | maintenance_invoice | correspondence
""".strip(),
    },
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Tenant Blacklist Policy",
        "metadata": {"section": "blacklist"},
        "text": """
TENANT BLACKLIST POLICY

GROUNDS FOR BLACKLISTING
  A tenant may be added to the company blacklist for:
  1. Consistent late or unpaid rent (3+ months in arrears).
  2. Deliberate or negligent damage to a company property.
  3. Illegal or immoral use of a leased unit.
  4. Abandonment of a unit mid-lease without notice.
  5. Serious or repeated violation of building rules after formal warnings.
  6. Fraudulent identity documents submitted during KYC.

BLACKLISTING PROCESS
  - The Leasing Agent documents the grounds with evidence.
  - Property Manager reviews and approves the blacklist request.
  - The tenant's record in the system is flagged is_blacklisted = true.
  - A formal notice is sent to the tenant explaining the decision.

EFFECT OF BLACKLISTING
  - The system prevents new leases from being created for blacklisted tenants.
  - Current lease (if any) is reviewed for potential termination based on
    the specific grounds.

APPEAL PROCESS
  A blacklisted tenant may appeal by:
  1. Submitting a written request to the Property Manager.
  2. Providing supporting evidence contesting the blacklist grounds.
  Appeals are reviewed within 30 business days.
  If the appeal is upheld, the blacklist flag is removed.
""".strip(),
    },
    {
        "source": "lease_policies",
        "doc_type": "policy",
        "title": "Ejari Registration Policy",
        "metadata": {"section": "ejari"},
        "text": """
EJARI REGISTRATION POLICY

WHAT IS EJARI?
  Ejari (meaning "My Rent") is Dubai's mandatory tenancy registration system
  operated by the Dubai Land Department (DLD). Every tenancy contract in Dubai
  must be registered with Ejari.

REGISTRATION OBLIGATION
  - All leases must be registered within 30 days of signing by both parties.
  - Registration is the tenant's responsibility unless agreed otherwise in writing.
  - The Ejari number and registration date are recorded in the lease record.

WHAT YOU NEED FOR EJARI REGISTRATION
  - Signed tenancy contract (original)
  - Tenant's passport and Emirates ID copies
  - Landlord's title deed (the company provides this on request)
  - DEWA premises number for the unit
  - Previous Ejari certificate (for renewals)

HOW TO REGISTER
  - Online via the Dubai REST app or DLD Ejari portal.
  - In person at an authorised Ejari typing centre.
  - Via the company's partner typing centre (ask the Leasing Agent).

IMPORTANCE OF EJARI
  The Ejari certificate is required for:
  - DEWA (water and electricity) connection in the tenant's name.
  - UAE residency visa applications linked to the property.
  - Trade licence renewals (for commercial units).
  - Filing a case at the Rental Dispute Settlement Centre (RDSC).

RENEWAL EJARI
  A new Ejari certificate must be obtained for every renewed lease.
  The old Ejari certificate must be cancelled before a new one can be issued.
""".strip(),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 2. TENANT FAQ
# ══════════════════════════════════════════════════════════════════════════════

TENANT_FAQ: list[dict[str, Any]] = [
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "How do I connect DEWA (water and electricity) for my unit?",
        "metadata": {"topic": "dewa"},
        "text": """
Q: How do I connect DEWA for my new unit?

A: DEWA connection is the tenant's responsibility and must be set up before or on
move-in day. Here is the process:

1. OBTAIN YOUR EJARI CERTIFICATE
   You need a valid Ejari certificate (registered tenancy contract) before DEWA
   will process your application. Ask your Leasing Agent for the DEWA premises
   number of your unit.

2. APPLY FOR DEWA CONNECTION
   - Online: visit the DEWA website (dewa.gov.ae) or use the DEWA Smart app.
   - In person: visit a DEWA customer service centre.
   - Documents needed: Ejari certificate, passport copy, Emirates ID copy,
     and the DEWA premises number.

3. SECURITY DEPOSIT (FINANCE TEAM)
   DEWA requires a refundable security deposit. Contact the Finance team for
   guidance on deposit amounts — this is outside the scope of lease management.

4. TIMELINE
   DEWA activation typically takes 1–3 business days after application.
   Plan your move-in date accordingly.

5. DISCONNECTION ON MOVE-OUT
   You are responsible for disconnecting DEWA in your name before handover.
   Failure to disconnect may result in continued billing in your name.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "Can I sublet my unit or list it on Airbnb?",
        "metadata": {"topic": "subletting"},
        "text": """
Q: Can I sublet my unit or rent it out on Airbnb / short-term rental platforms?

A: No — subletting is prohibited without written approval from the Property Manager.

SUBLETTING RULES
  Under RERA Law 33 and your tenancy agreement, you may not sublet or assign
  your lease to any other person without the company's written consent.
  This applies to:
  - Subletting a room to a flatmate (even informally).
  - Full subletting while you travel.
  - Any short-term or holiday rental arrangement.

SHORT-TERM RENTALS (AIRBNB, BOOKING.COM, ETC.)
  Dubai requires a separate Holiday Home Permit from the Dubai Tourism and
  Commerce Marketing (DTCM) department for short-term rentals. Operating
  without this permit is illegal and may result in fines.

  Even with a DTCM permit, you must have the company's written consent.

HOW TO REQUEST SUBLETTING APPROVAL
  Submit a written request to your Leasing Agent explaining:
  - Who the proposed subtenant is (with ID documents).
  - The proposed duration.
  - Why you need to sublet.
  The Property Manager reviews requests within 10 business days.

CONSEQUENCES OF UNAUTHORISED SUBLETTING
  Unauthorised subletting is grounds for lease termination under RERA Law 33.
  The company will also notify the relevant authorities if required.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "Are pets allowed in my unit?",
        "metadata": {"topic": "pets"},
        "text": """
Q: Am I allowed to keep a pet in my unit?

A: Pets are permitted only in buildings designated as pet-friendly.
   Check your unit details or ask your Leasing Agent to confirm whether
   your building allows pets.

PET-FRIENDLY BUILDINGS
  Not all buildings in the portfolio are pet-friendly. Buildings that allow
  pets will have this noted in the unit description. If your building is not
  pet-friendly, pets are not permitted under any circumstances.

IF YOUR BUILDING IS PET-FRIENDLY
  You must notify the Property Manager in writing before bringing a pet.
  Permitted pets: cats, small dogs, small caged birds, and fish.
  Restricted breeds: large dog breeds restricted by Dubai Municipality
  (e.g. Pit Bull, Rottweiler, Dobermann) require special permits.

PET RULES IN PET-FRIENDLY BUILDINGS
  - Pets must be kept on a lead in all common areas.
  - Pet waste must be cleaned up immediately in all common areas.
  - Pets must not cause excessive noise that disturbs neighbours.
  - Damage caused by pets is the tenant's responsibility and is not
    considered fair wear and tear.

EXOTIC ANIMALS
  Exotic animals (reptiles, large primates, big cats) are prohibited under
  Dubai Municipality regulations regardless of building type.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "What happens if my Emirates ID or visa expires during my lease?",
        "metadata": {"topic": "document expiry"},
        "text": """
Q: My Emirates ID / visa is expiring during my lease. What should I do?

A: You must renew your documents and provide updated copies to the Leasing Agent.

TIMELINE
  - Notify your Leasing Agent as soon as you know your document is expiring.
  - Provide updated document copies within 14 days of expiry.
  - The system will flag your document as expired and your Leasing Agent
    will contact you automatically 30 days before expiry.

WHY THIS MATTERS
  Your tenancy agreement requires you to maintain valid residency documents
  throughout the lease term. Expired documents may affect:
  - Your ability to renew the lease.
  - Ejari registration for the renewal.
  - DEWA and other utility accounts.

WHAT TO SUBMIT
  - Updated passport copy (if renewed).
  - Updated UAE Residency Visa copy.
  - Updated Emirates ID copy.
  Submit these to your Leasing Agent in person or by email.

IF YOUR VISA IS CANCELLED
  If your UAE residency visa is cancelled (e.g., you leave your job),
  contact your Leasing Agent immediately to discuss your options.
  A grace period of 30 days typically applies, but this varies by situation.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "Can I make alterations or modifications to my unit?",
        "metadata": {"topic": "alterations"},
        "text": """
Q: Can I paint the walls, install shelves, or make modifications to my unit?

A: Minor alterations require written approval; major alterations are generally not permitted.

MINOR ALTERATIONS (REQUIRE WRITTEN APPROVAL)
  The following require a written request to the Property Manager:
  - Painting walls (you must repaint to the original colour on move-out).
  - Installing curtain rods, TV brackets, or shelving (minor drilling).
  - Installing additional air conditioning (must be a licensed contractor).

HOW TO REQUEST
  Submit a written request to your Leasing Agent describing the planned alteration.
  The Property Manager will respond within 5 business days.
  Keep a copy of the approval for your records.

MAJOR ALTERATIONS (NOT PERMITTED)
  The following are not permitted without a separate written agreement:
  - Structural changes (removing or adding walls, partitioning).
  - Changing floor tiles or permanent flooring.
  - Modifying electrical systems or plumbing.
  - Installing satellite dishes or external fixtures visible from outside.

RESTORATION ON MOVE-OUT
  Any approved alterations must be restored to their original state on move-out
  unless otherwise agreed in writing. Costs of restoration are borne by the tenant.

UNAPPROVED ALTERATIONS
  Unapproved alterations may result in a formal warning and/or charges for
  restoration at move-out. Significant unapproved alterations are grounds
  for lease termination.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "How do I raise a maintenance request?",
        "metadata": {"topic": "maintenance"},
        "text": """
Q: Something is broken in my unit. How do I raise a maintenance request?

A: You can raise a maintenance request through the Lease Manager Agent (this system)
   or by contacting your Leasing Agent directly.

PRIORITY LEVELS AND RESPONSE TIMES
  Emergency (respond within 1 hour):
    - Flooding or major water leak
    - Gas leak (call Etisalat Gas on 04-806-1313 immediately, then log the request)
    - Fire risk (call 997 first, then log)
    - Total power outage affecting the entire unit
    - Broken front door lock (security risk)

  High (resolve within 6 hours):
    - Air conditioning failure (HVAC) — especially critical in summer months
    - Hot water failure
    - Partial power loss (specific circuits)
    - Blocked or leaking toilet (main toilet)

  Medium (resolve within 48 hours / 2 business days):
    - Appliance failure (oven, dishwasher, washing machine)
    - Minor plumbing issues (dripping taps, slow drains)
    - Damaged fixtures or fittings

  Low (resolve within 120 hours / 5 business days):
    - Cosmetic issues (paint peeling, minor cracks)
    - Non-urgent carpentry (door that doesn't close flush)
    - Cleaning requests

WHAT HAPPENS AFTER YOU RAISE A REQUEST
  1. You receive a confirmation with a reference number (e.g. MR-2026-001234).
  2. A technician is assigned to your request.
  3. You are notified when the technician is on their way.
  4. After completion, you are asked to rate the service (1–5 stars).

TENANT OBLIGATIONS
  - You must provide reasonable access for the maintenance team.
  - Damage caused by tenant misuse is the tenant's responsibility.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "What is the parking situation in the building?",
        "metadata": {"topic": "parking"},
        "text": """
Q: How many parking spaces do I get? Can I have visitors park in the building?

A: Parking allocation depends on your unit type and the specific building.

ALLOCATED PARKING
  - Studio and 1-bedroom units: typically 1 covered parking space.
  - 2-bedroom units: typically 1–2 covered parking spaces.
  - 3-bedroom and larger units: typically 2 covered parking spaces.
  - Penthouse units: 2–4 spaces (varies by building).
  - Commercial units: as specified in the lease.
  Your parking bay number is indicated in your tenancy contract.

VISITOR PARKING
  Visitor parking is available in designated visitor areas on a first-come,
  first-served basis. Maximum stay: 4 hours. Overnight visitor parking is
  not permitted without prior approval from building management.

ADDITIONAL PARKING
  If you need an additional parking space, contact your Leasing Agent.
  Additional spaces are available subject to building availability and
  an additional monthly fee (handled by the Finance team).

PARKING RULES
  - Park only in your allocated bay.
  - Do not block other bays, fire lanes, or building entrances.
  - Electric vehicle charging stations are available in some buildings
    (ask your Leasing Agent).
  - Abandoned vehicles will be reported to Dubai Police.
""".strip(),
    },
    {
        "source": "tenant_faq",
        "doc_type": "faq",
        "title": "What are the building rules I need to follow?",
        "metadata": {"topic": "building rules"},
        "text": """
Q: What are the rules for living in the building?

A: All tenants must follow the building rules. Key rules are:

NOISE
  - Keep noise within acceptable levels at all times.
  - Quiet hours: 10:00 PM to 8:00 AM (no loud music, parties, or power tools).
  - Noise complaints can be raised with building management or Dubai Police.

COMMON AREAS
  - Keep lobbies, lifts, stairwells, and corridors clear at all times.
  - No storage of items in common areas (bicycles, boxes, furniture).
  - Children must be supervised in common areas and play areas.

RUBBISH AND RECYCLING
  - Dispose of rubbish in designated bins only.
  - Recycling facilities are available — please use them.
  - Do not leave rubbish bags in corridors.

BALCONIES
  - No hanging laundry or items visible from outside on balconies.
  - No throwing items from balconies (legal offence in Dubai).
  - Balcony furniture must be secured in windy conditions.

SMOKING
  - Smoking is prohibited in all indoor common areas, lifts, and corridors.
  - Designated smoking areas are available in some buildings.
  - Ask building management for the location.

MOVING FURNITURE
  - Large furniture moves must be pre-booked with building management.
  - Moving during quiet hours is not permitted.
  - Use the designated service lift for moving furniture.

VIOLATIONS
  A formal warning is issued for each violation. Three warnings may result
  in lease termination proceedings.
""".strip(),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 3. MOVE-IN GUIDELINES
# ══════════════════════════════════════════════════════════════════════════════

MOVE_IN_GUIDELINES: list[dict[str, Any]] = [
    {
        "source": "move_in_guidelines",
        "doc_type": "guideline",
        "title": "Move-In Pre-Conditions Checklist",
        "metadata": {"section": "pre-conditions"},
        "text": """
MOVE-IN PRE-CONDITIONS CHECKLIST

Before the tenant moves in, ALL of the following must be confirmed:

LEASE STATUS
  ☐ Lease status is ACTIVE (both parties have signed, Ejari is registered).
  ☐ Ejari certificate has been issued and a copy is on file.
  ☐ Unit status is updated from "reserved" to "occupied" in the system.

DOCUMENTS
  ☐ Passport, Emirates ID, and Visa copies are verified (status: verified).
  ☐ Signed tenancy contract copy has been issued to the tenant.
  ☐ Ejari certificate copy has been issued to the tenant.

UNIT READINESS
  ☐ All previously reported maintenance items are resolved.
  ☐ Unit has been professionally cleaned.
  ☐ All appliances are tested and functioning:
       Air conditioning | Water heater | Oven/hob | Dishwasher |
       Washing machine | Fridge/freezer | Intercom | Door locks
  ☐ All light fittings are working.
  ☐ All windows and doors open and close properly.
  ☐ No leaks in bathrooms, kitchen, or balcony.

KEYS AND ACCESS
  ☐ Main door key(s) prepared.
  ☐ Building access card(s) prepared.
  ☐ Parking remote/fob prepared (if applicable).
  ☐ Letterbox key prepared.
  ☐ Pool/gym access card prepared (if applicable).

DEWA
  ☐ Tenant has applied for DEWA connection in their name.
  ☐ DEWA is active on the day of move-in.
     (The unit should NOT be handed over without active DEWA.)
""".strip(),
    },
    {
        "source": "move_in_guidelines",
        "doc_type": "guideline",
        "title": "Move-In Inspection Process",
        "metadata": {"section": "inspection"},
        "text": """
MOVE-IN INSPECTION PROCESS

The move-in inspection is a mandatory joint walkthrough conducted by the Leasing Agent
and the tenant on or before the first day of the lease.

PURPOSE
  To document the exact condition of the unit at handover so that any damage
  at move-out can be distinguished from pre-existing issues or fair wear and tear.

WHAT IS INSPECTED
  For each room: walls, ceiling, floor, windows, doors.
  Kitchen: all appliances, cabinets, sink, taps, extractor fan.
  Bathrooms: toilet, shower/bath, taps, mirror, towel rails.
  Balcony/terrace: tiles, railings, drain.
  Common: air conditioning units (all), light switches, power sockets,
          intercom, fire alarm panel, water meter reading.

HOW IT WORKS
  1. The Leasing Agent and tenant walk through every room together.
  2. Any existing defects (scratches, dents, stains, damage) are noted on the
     move-in checklist with descriptions and photographs.
  3. Both parties sign the completed move-in checklist.
  4. Each party receives a copy; one copy is filed in the tenant's document record.

AFTER THE INSPECTION
  - Any defects noted during inspection are logged as maintenance requests.
  - Defects caused by the previous tenant are the company's responsibility to fix.
  - The tenant is not responsible for pre-existing defects documented at move-in.

KEYS AND ACCESS HANDOVER
  After the inspection and signed checklist, the Leasing Agent hands over:
  - All keys and access cards listed in the pre-conditions checklist.
  - A welcome pack with building rules, emergency contacts, and useful information.
  - Contact details for the Leasing Agent and the maintenance team.
""".strip(),
    },
    {
        "source": "move_in_guidelines",
        "doc_type": "guideline",
        "title": "First Week in Your New Unit — Setup Guide",
        "metadata": {"section": "setup"},
        "text": """
FIRST WEEK IN YOUR NEW UNIT — SETUP GUIDE

IMMEDIATE PRIORITIES (DAY 1)
  1. Confirm DEWA is active. If not, contact DEWA at 04-601-9999.
  2. Test all appliances listed on your move-in checklist.
  3. Report any issues not noted on the move-in checklist immediately
     (within 48 hours) to your Leasing Agent. Issues reported later may
     be considered tenant-caused damage.
  4. Locate the main water stopcock and electricity fuse box.
     Know how to shut them off in an emergency.

WITHIN THE FIRST WEEK
  - Register for internet/TV: du or Etisalat/e& provide building connection.
    Check with building management which provider serves your building.
  - DEWA Green Account: register online to manage your DEWA account digitally.
  - Visitor parking: inform regular visitors about the 4-hour visitor parking rule.
  - Building access: test all access cards in all relevant areas (gym, pool, lobby).
  - Waste disposal: locate all recycling and waste disposal points.

EMERGENCY CONTACTS TO SAVE
  - Maintenance emergency line: [see welcome pack for current number]
  - DEWA: 04-601-9999
  - Dubai Police: 999
  - Ambulance: 998
  - Dubai Civil Defence (fire): 997
  - Gas emergency (Etisalat Gas): 04-806-1313
  - Your Leasing Agent: [see your contract for contact details]

REGISTER YOUR VEHICLE
  If you have a vehicle, register the number plate with building management
  for your parking bay allocation and access permissions.
""".strip(),
    },
    {
        "source": "move_in_guidelines",
        "doc_type": "guideline",
        "title": "Building Access and Key Policy",
        "metadata": {"section": "keys"},
        "text": """
BUILDING ACCESS AND KEY POLICY

KEYS AND ACCESS CARDS ISSUED AT MOVE-IN
  You will be issued with all necessary keys and access cards at move-in.
  A record of all items issued is included in your signed move-in checklist.

LOST KEYS OR ACCESS CARDS
  Report lost keys or access cards to building management immediately.
  Replacement charges apply:
  - Main door key: typically AED 50–150 per key (varies by lock type).
  - Building access card: typically AED 50–100 per card.
  - Parking remote/fob: typically AED 100–250 per unit.
  Charges for replacements are handled by the Finance team.

LOCKOUTS
  If you are locked out of your unit during business hours (8am–5pm),
  contact your Leasing Agent.
  Outside business hours, contact the building security team.
  There may be a call-out charge for out-of-hours lockouts.

KEY DUPLICATION
  You may not duplicate keys without written approval from building management.
  Access card duplication is not possible (cards are electronically programmed).

RETURN ON MOVE-OUT
  ALL keys, access cards, parking fobs, and letterbox keys MUST be returned
  on the last day of the lease. Lost items at move-out will be charged to
  the tenant.
""".strip(),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 4. MOVE-OUT GUIDELINES
# ══════════════════════════════════════════════════════════════════════════════

MOVE_OUT_GUIDELINES: list[dict[str, Any]] = [
    {
        "source": "move_out_guidelines",
        "doc_type": "guideline",
        "title": "Move-Out Notice Requirements",
        "metadata": {"section": "notice"},
        "text": """
MOVE-OUT NOTICE REQUIREMENTS

NOTICE PERIOD
  The required notice period is stated in your tenancy contract.
  The default notice period is 60 days unless otherwise agreed.
  Check your lease for your specific notice period before planning your move-out.

HOW TO GIVE NOTICE
  Written notice is required. Accepted methods:
  - Email to your Leasing Agent (keep a copy in your sent folder).
  - Registered mail to the company's registered address.
  Verbal notice is NOT accepted.

WHAT TO INCLUDE IN YOUR NOTICE
  - Your full name.
  - Your lease number (e.g. LSE-2026-001234).
  - Your unit number and building name.
  - Your intended vacate date.
  - A statement that you are giving notice under the notice period clause.

LATE NOTICE
  If you give notice with less than the required notice period:
  - You may be liable for rent for the full notice period regardless of when
    you vacate. Contact the Finance team to understand the financial implications.
  - The Leasing Agent will record the actual notice date in the system.

CONFIRMING YOUR VACATE DATE
  Your Leasing Agent will confirm receipt of your notice and your vacate date
  in writing within 3 business days.

EARLY VACATE (BEFORE LEASE END DATE)
  Vacating early without completing the notice period may incur penalties.
  Contact the Finance team for guidance on early termination costs.
""".strip(),
    },
    {
        "source": "move_out_guidelines",
        "doc_type": "guideline",
        "title": "Move-Out Inspection Process",
        "metadata": {"section": "inspection"},
        "text": """
MOVE-OUT INSPECTION PROCESS

SCHEDULING THE INSPECTION
  A move-out inspection must be scheduled within 7 days of your written notice.
  Your Leasing Agent will contact you to arrange a date and time.
  The inspection should ideally be done 3–7 days before your vacate date so
  any agreed remediation can be completed in time.

WHAT TO PREPARE FOR THE INSPECTION
  - Remove all your belongings before the inspection.
  - Ensure the unit is clean (professionally cleaned is recommended).
  - Ensure all appliances are clean and in working order.
  - Patch and repaint any unapproved holes or marks.
  - Replace any broken items you are responsible for.

WHAT IS ASSESSED
  The inspector compares the current condition against the move-in checklist:
  - Walls: marks, holes, stains beyond fair wear and tear.
  - Floors: scratches, stains, damaged tiles.
  - Appliances: functional and clean.
  - Bathrooms: clean, no damage beyond fair wear and tear.
  - Kitchen: clean, no damage to surfaces, cabinets, or appliances.
  - Windows and doors: functioning, no broken glass or damaged locks.
  - AC units: clean filters, functional.

FAIR WEAR AND TEAR
  Fair wear and tear is the normal deterioration from everyday use. This is
  NOT chargeable to the tenant. Examples:
  - Scuff marks at floor level from furniture.
  - Faded paint in areas exposed to sunlight.
  - Slight carpet pile compression from furniture.

CHARGEABLE DAMAGE (BEYOND FAIR WEAR AND TEAR)
  The following are typically chargeable:
  - Holes in walls from unapproved drilling.
  - Stained or burnt carpet or flooring.
  - Broken fittings or appliances due to misuse.
  - Pet damage (scratches, stains).
  - Unapproved alterations not restored.
  Charges are assessed by the Property Manager and billed by the Finance team.
""".strip(),
    },
    {
        "source": "move_out_guidelines",
        "doc_type": "guideline",
        "title": "Unit Handover and Key Return Process",
        "metadata": {"section": "handover"},
        "text": """
UNIT HANDOVER AND KEY RETURN PROCESS

ON YOUR LAST DAY
  Complete ALL of the following before handing over the unit:

  DEWA DISCONNECTION
  ☐ Contact DEWA to close your account and arrange a final meter reading.
     Submit a DEWA clearance letter if required by building management.

  CLEANING
  ☐ The unit must be clean, empty, and in a condition consistent with the
     move-in checklist (fair wear and tear excepted).
  ☐ Professional cleaning is strongly recommended.

  KEYS AND ACCESS CARDS
  ☐ Return ALL keys, access cards, parking fobs, and letterbox keys to the
     Leasing Agent. Any missing items will be charged to you.
  ☐ The Leasing Agent will sign a key return receipt — keep your copy.

  PERSONAL BELONGINGS
  ☐ Remove ALL personal belongings. Any items left in the unit after the
     handover date may be disposed of without liability to the company.

  PARKING
  ☐ Remove your vehicle(s) from your allocated parking bay.

AFTER HANDOVER
  - The Leasing Agent will conduct the final inspection within 24 hours.
  - A post-handover report will be sent to you within 5 business days.
  - Any chargeable damage will be documented and referred to the Finance team.
  - Ejari cancellation will be processed by the company within 7 days.
  - Unit status will be updated to "available" once handover is accepted.
""".strip(),
    },
    {
        "source": "move_out_guidelines",
        "doc_type": "guideline",
        "title": "Ejari Cancellation on Move-Out",
        "metadata": {"section": "ejari_cancellation"},
        "text": """
EJARI CANCELLATION ON MOVE-OUT

WHY EJARI CANCELLATION MATTERS
  The Ejari registration links your tenancy to the unit in the Dubai Land
  Department's records. If the Ejari is not cancelled after you vacate,
  the unit cannot be legally re-rented to a new tenant.
  Uncancelled Ejari registrations can also affect the tenant's credit record.

WHO HANDLES CANCELLATION
  The company processes the Ejari cancellation on your behalf within 7 days
  of lease termination or expiry. You do not need to take any action.

WHAT YOU NEED TO PROVIDE
  If the company requests any documents to facilitate cancellation:
  - Final DEWA bill or clearance letter (confirming account closure in your name).
  - Copy of your original Ejari certificate.
  These will typically be requested at handover.

CONFIRMATION
  Once the Ejari cancellation is processed, you will receive a confirmation
  from the Dubai Land Department. The company will forward this to you.

IMPORTANT FOR TENANTS LEAVING THE UAE
  If you are leaving the UAE, ensure the Ejari is cancelled before departure.
  An uncancelled Ejari will not prevent your visa cancellation but may create
  complications for future property dealings in Dubai.
""".strip(),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# 5. RENEWAL POLICIES
# ══════════════════════════════════════════════════════════════════════════════

RENEWAL_POLICIES: list[dict[str, Any]] = [
    {
        "source": "renewal_policies",
        "doc_type": "policy",
        "title": "RERA Law 33 — 90-Day Notice Rule for Renewals",
        "metadata": {"section": "rera_notice", "law": "Law 33/2008"},
        "text": """
RERA LAW 33 — 90-DAY NOTICE RULE

THE RULE
  Under RERA Law No. 33 of 2008, Article 25:
  If a landlord does not intend to renew a tenancy contract, they must give the
  tenant at least 90 days written notice before the lease expiry date.

  Equally, if the tenant does not intend to renew, they must give the landlord
  at least 90 days notice (or as per the notice period in the contract, whichever
  is greater).

HOW NOTICE MUST BE SERVED
  Notice must be given in one of the following ways:
  - Via a Notary Public (in person or online through the Dubai Courts).
  - Via registered mail (with proof of delivery).
  Email and WhatsApp are NOT sufficient for RERA-compliant non-renewal notice.

CONSEQUENCES OF FAILING TO GIVE NOTICE
  IF THE LANDLORD FAILS TO GIVE 90 DAYS NOTICE:
  - The landlord cannot legally refuse renewal on grounds of non-renewal.
  - The lease automatically renews under the same terms for the same period.

  IF THE TENANT FAILS TO GIVE 90 DAYS NOTICE:
  - The tenant may be liable for rent beyond the lease end date.
  - The company may retain the right to enforce the full notice period.

RERA COMPLIANCE IN THE SYSTEM
  When a renewal is initiated, the system calculates:
  - notice_due_by = lease end date − 90 days
  - rera_notice_compliant = today ≤ notice_due_by
  If rera_notice_compliant is false, the Leasing Agent is warned and must
  document the reason for the late notice.

KEY DATES FOR LEASE RENEWAL PIPELINE
  - 120 days before expiry: Leasing Agent initiates renewal discussion.
  - 90 days before expiry: RERA notice deadline.
  - 60 days before expiry: Tenant must have confirmed renewal or non-renewal.
  - 30 days before expiry: New Ejari prepared for renewal cases.
""".strip(),
    },
    {
        "source": "renewal_policies",
        "doc_type": "policy",
        "title": "RERA Rent Increase Calculator — Maximum Permitted Increases",
        "metadata": {"section": "rent_increase", "decree": "Decree 43/2013"},
        "text": """
RERA RENT INCREASE CALCULATOR (DECREE NO. 43 OF 2013)

HOW RENT INCREASES ARE REGULATED
  Rent increases upon lease renewal are strictly capped by RERA based on how far
  the current rent falls below the RERA market average for comparable units in
  the same area.

PERMITTED INCREASE TABLE
  Current rent vs. RERA market average     Maximum permitted increase
  ─────────────────────────────────────────────────────────────────────
  Up to 10% below market rate              0%  (no increase)
  11% – 20% below market rate              5%  maximum
  21% – 30% below market rate              10% maximum
  31% – 40% below market rate              15% maximum
  More than 40% below market rate          20% maximum

HOW TO CHECK THE RERA RENTAL INDEX
  Tenants and landlords can check the current RERA rental index via:
  - Dubai REST app (official Dubai Land Department app).
  - DLD website (dubailand.gov.ae) — Rental Index section.
  - At any Ejari typing centre.

DISPUTING A RENT INCREASE
  If the proposed increase exceeds the permitted cap, the tenant can:
  1. Raise the issue with the Leasing Agent/Property Manager first.
  2. File a case with the Rental Dispute Settlement Centre (RDSC).
     Filing fee: 3.5% of annual rent (min AED 500, max AED 15,000).

AGENT OBLIGATION
  When initiating a renewal, the Leasing Agent must:
  - Check the current RERA index for the unit type and area.
  - Ensure the proposed rent increase does not exceed the permitted cap.
  - Document the RERA index reference in the renewal record.
""".strip(),
    },
    {
        "source": "renewal_policies",
        "doc_type": "policy",
        "title": "Lease Renewal Process — Step by Step",
        "metadata": {"section": "process"},
        "text": """
LEASE RENEWAL PROCESS — STEP BY STEP

TIMELINE
  Day −120 (4 months before expiry): Leasing Agent flags lease for renewal review.
  Day −90  (3 months before expiry): RERA notice deadline — must initiate by this date.
  Day −60  (2 months before expiry): Tenant response deadline.
  Day −30  (1 month before expiry):  New Ejari preparation.
  Day 0    (lease end date):         New lease term begins (if renewed).

STEP 1 — INITIATE RENEWAL OFFER
  The Leasing Agent prepares a renewal offer including:
  - New lease start date (day after current lease end date).
  - Proposed new lease end date (typically 12 months later).
  - Proposed new annual rent (must comply with RERA increase limits).
  - A copy of the current RERA index for the unit's area and type.
  A Renewal record is created in the system with status "offered".

STEP 2 — SEND THE OFFER
  The renewal offer is sent to the tenant in writing:
  - By email AND registered mail (for RERA compliance).
  The offer letter must include the RERA-permitted increase percentage.

STEP 3 — TENANT RESPONSE (15-DAY WINDOW)
  Tenant has 15 days to respond with one of:
  - ACCEPTED — tenant agrees to the proposed terms.
  - COUNTER-OFFER — tenant proposes different rent amount.
  - REJECTED — tenant does not wish to renew.
  - NO RESPONSE — after 15 days, the offer lapses.

STEP 4 — NEGOTIATION (IF COUNTER-OFFER)
  If the tenant makes a counter-offer:
  - The Leasing Agent reviews and consults the Property Manager.
  - A revised offer may be issued or the original upheld.
  - Maximum 2 rounds of negotiation.

STEP 5 — FINALISE AND SIGN
  Once agreed:
  - A new tenancy contract is generated with the new terms.
  - Both parties sign digitally.
  - New Ejari is registered for the renewed term.
  - Old Ejari is cancelled.
  - Renewal record status updated to "accepted".
  - New Lease record created (if the system tracks each renewal as a new lease).

STEP 6 — IF TENANT REJECTS OR NO RESPONSE
  - Leasing Agent issues a formal non-renewal notice (if not already done).
  - Move-out inspection is scheduled per the move-out guidelines.
  - The unit is listed as available for new tenants.
""".strip(),
    },
    {
        "source": "renewal_policies",
        "doc_type": "policy",
        "title": "Automatic Renewal and Non-Renewal Scenarios",
        "metadata": {"section": "auto_renewal"},
        "text": """
AUTOMATIC RENEWAL AND NON-RENEWAL SCENARIOS

AUTOMATIC RENEWAL (DEFAULT)
  Under RERA Law 33, if neither party gives the required notice before lease expiry:
  - The lease automatically renews for the same period under the same terms.
  - The new rent cannot exceed the RERA permitted increase (even on auto-renewal).
  - A new Ejari certificate must still be obtained for the renewed term.

TENANT CHOOSES NOT TO RENEW
  The tenant must give written notice at least 90 days before expiry
  (or the notice period in the contract, whichever is greater).
  After notice:
  - The Renewal record is updated to status "rejected".
  - Move-out inspection is scheduled.
  - The unit is listed as available for new tenants after handover.

COMPANY CHOOSES NOT TO RENEW
  The company must give written notice via notary public or registered mail
  at least 90 days before expiry. Grounds for non-renewal include:
  - The company intends to sell the unit.
  - The landlord (company) or a first-degree relative needs it for personal use
    (requires 12 months notice under RERA Law 33, not 90 days).
  - Redevelopment or major renovation approved by authorities.
  If the company fails to give proper notice, the lease auto-renews.

WHAT HAPPENS IF THE TENANT STAYS AFTER LEASE EXPIRY?
  If the tenant remains in occupation after the lease expiry date:
  - Without renewal agreement: The company may file for eviction at the RDSC.
  - With auto-renewal (no notice given): The tenancy continues legally.
  The Leasing Agent must document the situation and seek Property Manager guidance.
""".strip(),
    },
    {
        "source": "renewal_policies",
        "doc_type": "policy",
        "title": "Renewal Record and System Workflow",
        "metadata": {"section": "system_workflow"},
        "text": """
RENEWAL RECORD AND SYSTEM WORKFLOW

RENEWAL STATUSES IN THE SYSTEM
  pending     — Renewal flagged; offer not yet sent to tenant.
  offered     — Renewal offer sent to tenant; awaiting response.
  accepted    — Tenant has accepted the renewal terms.
  rejected    — Tenant has declined to renew.
  lapsed      — No response from tenant within 15 days; offer expired.

CREATING A RENEWAL RECORD
  Use the "renew_lease" tool with:
  - lease_id: the UUID of the active lease.
  - new_end_date: proposed end date of the renewed term.
  - proposed_rent_aed: proposed annual rent for the new term.
  The system will automatically calculate notice_due_by and rera_notice_compliant.

DUPLICATE RENEWAL PREVENTION
  Only one open renewal (status: pending or offered) is allowed per lease at a time.
  If a renewal already exists, the system will return an error.
  Resolve or close the existing renewal before creating a new one.

AFTER RENEWAL IS ACCEPTED
  1. Generate new tenancy contract with new terms.
  2. Both parties sign the new contract digitally.
  3. Register new Ejari.
  4. Cancel old Ejari.
  5. Update the Renewal record: status → accepted, new_lease_id linked.
  6. The original lease record status remains ACTIVE until the new lease begins.

VIEW EXPIRING LEASES
  Use the "view_expiring_leases" tool to see which leases are expiring soon.
  The tool shows:
  - days_remaining until expiry.
  - rera_90day_notice_due_by: the RERA notice deadline.
  - rera_notice_window_open: whether the 90-day window is still open.
  - summary counts: urgent (≤30 days), within 60 days, RERA notice overdue.
""".strip(),
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

ALL_DOCUMENTS: list[dict] = (
    LEASE_POLICIES
    + TENANT_FAQ
    + MOVE_IN_GUIDELINES
    + MOVE_OUT_GUIDELINES
    + RENEWAL_POLICIES
)

# Source → human-readable label (used in retrieval context formatting)
SOURCE_LABELS: dict[str, str] = {
    "lease_policies": "Lease Policies",
    "tenant_faq": "Tenant FAQ",
    "move_in_guidelines": "Move-In Guidelines",
    "move_out_guidelines": "Move-Out Guidelines",
    "renewal_policies": "Renewal Policies",
}
