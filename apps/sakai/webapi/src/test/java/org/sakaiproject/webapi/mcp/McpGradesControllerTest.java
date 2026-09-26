/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 */
package org.sakaiproject.webapi.mcp;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.List;
import java.util.Map;

import org.junit.Test;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.grading.api.Assignment;
import org.sakaiproject.grading.api.GradeDefinition;
import org.sakaiproject.grading.api.GradingAuthz;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.grading.api.SortType;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.Session;
import org.sakaiproject.tool.api.SessionManager;

public class McpGradesControllerTest {

    @Test
    public void returnsOnlyCurrentUsersReleasedGradeEvenIfServiceReturnsOthers() throws Exception {
        SessionManager sessions = mock(SessionManager.class);
        Session session = mock(Session.class);
        when(sessions.getCurrentSession()).thenReturn(session);
        when(session.getUserId()).thenReturn("student-a");
        SiteService sites = mock(SiteService.class);
        Site site = mock(Site.class);
        when(sites.getSiteVisit("course-a")).thenReturn(site);
        when(site.getType()).thenReturn("course");
        when(site.getReference()).thenReturn("/site/course-a");
        SecurityService security = mock(SecurityService.class);
        when(security.unlock(GradingAuthz.PERMISSION_VIEW_OWN_GRADES, "/site/course-a")).thenReturn(true);
        GradingService grading = mock(GradingService.class);
        Assignment item = new Assignment();
        item.setId(7L);
        item.setName("Lab report");
        item.setReleased(true);
        when(grading.getViewableAssignmentsForCurrentUser("course-a", "course-a", SortType.SORT_BY_NONE))
                .thenReturn(List.of(item));
        GradeDefinition own = new GradeDefinition();
        own.setStudentUid("student-a");
        own.setGrade("77");
        GradeDefinition other = new GradeDefinition();
        other.setStudentUid("student-b");
        other.setGrade("31");
        when(grading.getGradesWithoutCommentsForStudentsForItems("course-a", "course-a", List.of(7L),
                List.of("student-a"))).thenReturn(Map.of(7L, List.of(other, own)));

        McpGradesController controller = new McpGradesController(sessions, sites, security, grading);
        List<McpGradesController.OwnGrade> grades = controller.ownGrades("course-a").get("grades");
        assertEquals(1, grades.size());
        assertEquals("77", grades.get(0).score());
        verify(grading).getGradesWithoutCommentsForStudentsForItems("course-a", "course-a", List.of(7L),
                List.of("student-a"));
    }
}
