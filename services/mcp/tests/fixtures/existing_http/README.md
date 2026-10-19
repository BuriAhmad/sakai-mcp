# Existing HTTP source-derived fixtures

These are synthetic **source-derived, unexercised** shapes for imported Sakai
25.2 (`b5b7800f0fcddf9d0db47276a66065189365d905`, root import `e092fa04`).
They are parser specifications, not captured serializer/permission/session proof.
No production routing switch is justified by these fixtures.

| Fixture | Source method | Remaining gate |
| --- | --- | --- |
| current_user | `UserEntityProvider.getCurrentUser`, `EntityUser` | Direct custom-action envelope, exact EID binding to validated OBO actor |
| site | `SiteEntityProvider.getEntity`, `EntitySite` | role masking of softlyDeleted, public-view visit boundary |
| user_permissions | `SiteEntityProvider.handleUserPerms` | custom-action Set encoding, effective unpublished/deleted permission scope |
| sites | `SitesController.getSites` | delegated WebAPI session, membership/visit equivalence, cap/large response |
| student/grader_grades | `GradesController.gradeDataSupplierForSite` | student-only pre-request guard, maxima/item correlation; blocked descriptor |
| submission_metadata/detail | `AssignmentEntityProvider.submissionToMap` | scope, actual envelope, active render mode, dropped/hidden fields; blocked descriptors |
| assignment_discovery | `AssignmentEntityProvider.getAssignmentsForSite`, `SimpleAssignment(a,true)` | site-wide-only bounded discovery; native entitlement/hydration, group-only UI and delegated/cold serializer acceptance pending |
| announcement_collection | `AnnouncementEntityProviderImpl.getAnnouncementsForSite`, EntityEncodingManager | native provider/codec characterized locally; merged/role/decoration completeness explicitly unverified, public complete=false |

The models discard unused native metadata. Missing, explicit null, and false are
distinct. No fixture invents raw gradeReleased, lockVersion, or completeness.
XML/SOAP and hostile shapes are built explicitly in tests, with the same unexercised
status. Dynamic browser controls remain source candidates until rendered captures
are authorized; parser tests cannot manufacture exercised evidence.
