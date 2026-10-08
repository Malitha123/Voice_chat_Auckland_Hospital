# NZ health assistant privacy considerations

This project uses synthetic patient data and is not affiliated with Health New Zealand. The privacy controls below describe the intended application boundaries. Any real deployment requires organisation-approved contacts, recipients, retention schedules, data-processing arrangements, and formal compliance review.

## NZ basis and intended use

The NZ policy basis is the Privacy Act 2020, the [Health Information Privacy Code 2020](https://www.privacy.org.nz/privacy-principles/codes-of-practice/hipc2020/) and the [Code of Health and Disability Services Consumers’ Rights](https://www.hdc.org.nz/your-rights/about-the-code/code-of-health-and-disability-services-consumers-rights/). The Privacy Commissioner lists the amended health code in force from 1 May 2026. HIPAA requirements depend on a US covered-entity/business-associate relationship; this NZ-focused implementation does not claim HIPAA coverage or certification. See [HHS covered entities and business associates](https://www.hhs.gov/hipaa/for-professionals/covered-entities/index.html).

The assistant helps a signed-in patient retrieve their own appointments and access general hospital information. It does not provide a substitute for clinical assessment. Personal records remain restricted to that signed-in account. Representative and family access must be handled through the clinic's verified process.

## Collection, notice and disclosure

Collect only the account identity, profile fields and conversation content needed for the requested service. Before collection, the clinic must explain the purpose, the agencies collecting/holding information, intended recipients, which fields are required, consequences of not supplying information and the access/correction process. Where information is collected indirectly, the clinic must assess the current notification requirements and applicable exceptions.

Voice use can send audio to LiveKit and the configured speech provider. Chat can send relevant conversation/profile context to the configured model provider. The clinic must approve those recipients and processing locations, provide an understandable notice and offer a suitable alternative channel. The code does not establish NZ-only processing or data residency. Do not infer consent for third-party access from a request, a shared surname or a phone number.

## Access, security and retention

Use verified credentials and active patient accounts. Check ownership before retrieving or changing appointments, memory or sessions. Keep credentials private, apply TLS and provider/gateway controls, and record authorised access with a suitable durable audit system. Sensitive traces stay disabled until an approved redaction and retention arrangement exists.

Patients should use the clinic's published process to request access to or correction of health information. Authentication alone does not implement the whole access-request procedure. The clinic must set retention and deletion schedules for databases, uploaded documents, model/speech providers, caches, audit records and backups. Deleting one chat session does not delete every retained copy or long-term fact.

## Human help and concerns

Provide a clinician or administrative handoff for disputed records, authorised representative requests and complaints. The clinic must supply its current privacy contact and incident-response process. For an emergency in New Zealand, call 111; the assistant must not delay urgent care.

Operational decisions still required: approved recipients and overseas processing arrangements, consent/notice wording, retention/deletion workflows, durable access auditing, delegated access, incident response and live identity-provider validation. These controls support those operational decisions without asserting that the application meets every legal obligation.
