/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 * http://www.opensource.org/licenses/ecl2
 */
package org.sakaiproject.sitemanage.impl.job;

import org.sakaiproject.authz.api.AuthzGroup;
import org.sakaiproject.authz.api.AuthzGroupService;
import org.sakaiproject.authz.api.Role;

/** Adds only the Student permission to see visible members of their course. */
final class StandardCourseRosterPermissions {
    static final String FUNCTION = "roster.viewallmembers";

    private StandardCourseRosterPermissions() { }

    static void ensureStudentAccess(AuthzGroupService service, String realmId) throws Exception {
        AuthzGroup realm = service.getAuthzGroup(realmId);
        Role student = realm.getRole("Student");
        if (student == null) {
            throw new IllegalStateException("Expected Student role is missing from realm " + realmId);
        }
        if (!student.isAllowed(FUNCTION)) {
            student.allowFunction(FUNCTION);
            service.save(realm);
        }
    }
}
