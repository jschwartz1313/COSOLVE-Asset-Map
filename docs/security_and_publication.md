# Security and publication

The public surface is deny-by-default. Public querysets require either `source-backed` or `published` status plus `public` visibility. Source-backed listings are explicitly labeled as awaiting editorial review. `Published` is reserved for records with completed editorial review dates. Dedicated public serializers omit internal notes, source notes, draft records, restricted records, and staff workflow fields. Admin, import, and export routes require a staff account and Django CSRF protection.

Publication workflow:

1. Create or import a draft.
2. Add at least one public source with a valid HTTP or HTTPS URL.
3. Review location precision and all public text.
4. Verify the source and record its verification date.
5. Mark the asset verified; this records the reviewer and review date.
6. Use the guarded publish action. Records without a dated, verified public source are skipped.
7. Archive stale or withdrawn records rather than deleting their history.

Assets, sources, relationships, saved views, and update submissions retain field-level revisions. The admin **History** view identifies the editor, timestamp, and reason and supports rollback. Automated link checks also retain source revisions.

Source monitoring rejects local, private, reserved, credential-bearing, non-HTTP, and nonstandard-port URLs before making a request. Redirect destinations are validated again. Automated failures can be marked accepted only with a staff explanation, or marked as requiring a replacement.

Direct login is rate-limited. Password recovery uses email, optional TOTP supplies a second factor and recovery codes, and optional OpenID Connect can connect an organization identity only to an active account that an administrator created in advance. Public account signup remains closed.

Never store or publish classified information, CUI, export-controlled technical data, live operational data, vulnerabilities, security procedures, or precise details that increase physical-security risk. The public viewer is an ecosystem-navigation product, not an operational map.

Before production, configure HTTPS, secure cookies, SMTP, restricted admin access, centralized logging, automated backups, and a tested restore process. Define role permissions and location-generalization rules with COSOLVE before adding partner-only data.
