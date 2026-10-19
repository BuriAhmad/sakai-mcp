/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.mockito.Mockito.mock;

import org.junit.Test;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.ContentHostingService;
import org.sakaiproject.grading.api.GradingAuthz;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.UserDirectoryService;
import org.sakaiproject.util.api.FormattedText;
import org.sakaiproject.webapi.mcp.assessment.McpAssessmentService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

import java.util.Set;
import java.util.stream.Collectors;

/** Exercise actual component scanning, constructor qualifiers, and the preserved grading routes. */
public class McpGradingWiringTest {
    @Test
    public void gradingComponentsWireAndKeepAllNativeRoutes() {
        try (var context = new AnnotationConfigApplicationContext()) {
            context.registerBean(
                    "org.sakaiproject.tool.api.SessionManager",
                    SessionManager.class,
                    () -> mock(SessionManager.class));
            context.registerBean(
                    "org.sakaiproject.grading.api.GradingService",
                    GradingService.class,
                    () -> mock(GradingService.class));
            context.registerBean(
                    "org.sakaiproject.grading.api.GradingAuthz",
                    GradingAuthz.class,
                    () -> mock(GradingAuthz.class));
            context.registerBean(AssignmentService.class, () -> mock(AssignmentService.class));
            context.registerBean(SiteService.class, () -> mock(SiteService.class));
            context.registerBean(SecurityService.class, () -> mock(SecurityService.class));
            context.registerBean(
                    ServerConfigurationService.class, () -> mock(ServerConfigurationService.class));
            context.registerBean(
                    UserDirectoryService.class, () -> mock(UserDirectoryService.class));
            context.registerBean(
                    ContentHostingService.class, () -> mock(ContentHostingService.class));
            context.registerBean(RubricsService.class, () -> mock(RubricsService.class));
            context.registerBean(FormattedText.class, () -> mock(FormattedText.class));
            context.registerBean(
                    McpAssessmentService.class, () -> mock(McpAssessmentService.class));
            context.scan("org.sakaiproject.webapi.mcp.grading");
            context.refresh();
            assertNotNull(context.getBean(McpGradeMutationService.class));
            assertNotNull(context.getBean(McpGradingProposalService.class));
            var mapping = new RequestMappingHandlerMapping();
            mapping.setApplicationContext(context);
            mapping.afterPropertiesSet();
            String root = "/mcp/v1/courses/{site}/assignments/{assignment}";
            var expected =
                    Set.of(
                            "GET " + root + "/grading-context",
                            "GET " + root + "/grading-submissions",
                            "GET " + root + "/grading-submissions/{submission}",
                            "GET " + root + "/grading-submissions/{submission}/files/{file}",
                            "GET " + root + "/grading-files/{file}",
                            "POST " + root + "/grading-proposals",
                            "GET " + root + "/grading-proposals/{proposal}",
                            "POST " + root + "/grading-exports",
                            "GET " + root + "/grading-exports/{export}",
                            "GET " + root + "/grading-exports/{export}/artifacts/{artifact}",
                            "POST " + root + "/grading-save",
                            "POST " + root + "/grading-release",
                            "POST " + root + "/grading-grades/query",
                            "GET " + root + "/grading-operations/{operation}",
                            "GET /mcp/v1/courses/{site}/grading-assignments");
            var actual =
                    mapping.getHandlerMethods().keySet().stream()
                            .flatMap(
                                    info ->
                                            info.getPatternsCondition().getPatterns().stream()
                                                    .flatMap(
                                                            path ->
                                                                    info
                                                                            .getMethodsCondition()
                                                                            .getMethods()
                                                                            .stream()
                                                                            .map(
                                                                                    method ->
                                                                                            method
                                                                                                            .name()
                                                                                                    + " "
                                                                                                    + path)))
                            .collect(Collectors.toSet());
            assertEquals(expected, actual);
        }
    }
}
