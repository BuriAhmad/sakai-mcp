/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.grading;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.mockito.Mockito.mock;

import java.util.Set;
import java.util.stream.Collectors;
import org.junit.Test;
import org.sakaiproject.assignment.api.AssignmentService;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.content.api.ContentHostingService;
import org.sakaiproject.grading.api.GradingService;
import org.sakaiproject.rubrics.api.RubricsService;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.user.api.UserDirectoryService;
import org.sakaiproject.webapi.mcp.assessment.McpAssessmentService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

/** Exercise actual component scanning, constructor qualifiers, and the preserved grading routes. */
public class McpGradingWiringTest {
  @Test
  public void gradingComponentsWireWithRetiredReadsAbsent() {
    try (var context = new AnnotationConfigApplicationContext()) {
      context.registerBean(
          "org.sakaiproject.tool.api.SessionManager",
          SessionManager.class,
          () -> mock(SessionManager.class));
      context.registerBean(
          "org.sakaiproject.grading.api.GradingService",
          GradingService.class,
          () -> mock(GradingService.class));
      context.registerBean(AssignmentService.class, () -> mock(AssignmentService.class));
      context.registerBean(SiteService.class, () -> mock(SiteService.class));
      context.registerBean(SecurityService.class, () -> mock(SecurityService.class));
      context.registerBean(
          ServerConfigurationService.class, () -> mock(ServerConfigurationService.class));
      context.registerBean(UserDirectoryService.class, () -> mock(UserDirectoryService.class));
      context.registerBean(ContentHostingService.class, () -> mock(ContentHostingService.class));
      context.registerBean(RubricsService.class, () -> mock(RubricsService.class));
      context.registerBean(McpAssessmentService.class, () -> mock(McpAssessmentService.class));
      context.scan("org.sakaiproject.webapi.mcp.grading");
      context.refresh();
      assertNotNull(context.getBean(McpGradingQueryService.class));
      assertEquals(
          Set.of("linked", "link", "writable"),
          java.util.Arrays.stream(McpGradebookProjection.class.getDeclaredMethods())
              .filter(m -> !m.isSynthetic())
              .map(java.lang.reflect.Method::getName)
              .collect(Collectors.toSet()));
      for (String retired : Set.of("revision", "current")) {
        org.junit.Assert.assertFalse(
            java.util.Arrays.stream(McpGradingEvidence.class.getDeclaredMethods())
                .anyMatch(m -> m.getName().equals(retired)));
      }
      for (String name :
          Set.of("McpGradingFileService", "McpGradingExportService", "McpGradingProposalService", "McpGradeMutationService")) {
        org.junit.Assert.assertThrows(
            ClassNotFoundException.class,
            () -> Class.forName("org.sakaiproject.webapi.mcp.grading." + name));
      }
      for (String name :
          Set.of(
              "McpAssessmentContextController",
              "McpAssignmentWriteController",
              "McpAssignmentSetupService")) {
        org.junit.Assert.assertThrows(
            ClassNotFoundException.class,
            () -> Class.forName("org.sakaiproject.webapi.mcp.assessment." + name));
      }
      var mapping = new RequestMappingHandlerMapping();
      mapping.setApplicationContext(context);
      mapping.afterPropertiesSet();
      String root = "/mcp/v1/courses/{site}/assignments/{assignment}";
      var expected =
          Set.of(
              "GET " + root + "/grading-context");
      var actual =
          mapping.getHandlerMethods().keySet().stream()
              .flatMap(
                  info ->
                      info.getPatternsCondition().getPatterns().stream()
                          .flatMap(
                              path ->
                                  info.getMethodsCondition().getMethods().stream()
                                      .map(method -> method.name() + " " + path)))
              .collect(Collectors.toSet());
      assertEquals(expected, actual);
    }
  }
}
