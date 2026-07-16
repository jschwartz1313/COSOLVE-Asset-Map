# Security and publication

The public surface is deny-by-default. Public querysets require `published` status and `public` visibility. Dedicated public serializers omit internal notes, source notes, draft records, restricted records, and staff workflow fields. Admin, import, and export routes require a staff account and Django CSRF protection.

Publication workflow:

1. Create or import a draft.
2. Add at least one acceptable public source.
3. Review location precision and all public text.
4. Mark the record verified and set `last_verified_at`.
5. Use the guarded publish action. Records without a public source are skipped.
6. Archive stale or withdrawn records rather than deleting their history.

Never store or publish classified information, CUI, export-controlled technical data, live operational data, vulnerabilities, security procedures, or precise details that increase physical-security risk. The public viewer is an ecosystem-navigation product, not an operational map.

Before production, configure HTTPS, secure cookies, restricted admin access, rate limiting at the proxy, centralized logging, automated backups, and a tested restore process. Define role permissions and location-generalization rules with COSOLVE before adding partner-only data.

