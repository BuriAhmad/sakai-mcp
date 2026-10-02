/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 * http://www.opensource.org/licenses/ecl2
 */
package org.sakaiproject.sitemanage.impl.job;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.Before;
import org.junit.Test;
import org.quartz.JobExecutionException;
import org.sakaiproject.authz.api.AuthzGroup;
import org.sakaiproject.authz.api.AuthzGroupService;
import org.sakaiproject.authz.api.Role;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.entity.api.ResourcePropertiesEdit;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SitePage;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.site.api.ToolConfiguration;
import org.sakaiproject.tool.api.Tool;
import org.sakaiproject.tool.api.ToolManager;

import static org.junit.Assert.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Regression checks for the v1 upgrade, privacy-scoped grant, and reruns. */
public class StandardCourseSetupTest {
    private ToolManager tools;
    private Site site;
    private List<SitePage> pages;
    private ResourcePropertiesEdit siteProperties;

    @Before
    public void setUp() {
        tools = mock(ToolManager.class);
        for (String id : StandardCourseLayout.requiredToolIds()) {
            Tool tool = mock(Tool.class);
            when(tool.getTitle()).thenReturn(id);
            when(tools.getTool(id)).thenReturn(tool);
        }
        site = mock(Site.class);
        pages = new ArrayList<>();
        when(site.getPages()).thenReturn(pages);
        when(site.addPage()).thenAnswer(invocation -> page());
        when(site.getId()).thenReturn("fixture-a");
        when(site.getType()).thenReturn("course");
        when(site.getReference()).thenReturn("/site/fixture-a");
        siteProperties = properties();
        when(site.getProperties()).thenReturn(siteProperties);
        when(site.getPropertiesEdit()).thenReturn(siteProperties);
    }

    @Test
    public void upgradeKeepsExistingPlacementsAndCustomPagesWithExactOverviewLayout() {
        SitePage assignments = page();
        ToolConfiguration originalAssignment = assignments.addTool();
        originalAssignment.setTool("sakai.assignment.grades", tools.getTool("sakai.assignment.grades"));
        SitePage custom = page();
        siteProperties.addProperty("sakai.course.layout.standard.migrated", "true");

        StandardCourseLayout.apply(site, tools);
        SitePage overview = pages.get(0);
        verify(overview).setTitle("Overview");
        verify(overview).setLayout(SitePage.LAYOUT_DOUBLE_COL);
        verify(findTool(overview, "sakai.iframe.site")).setLayoutHints("0,0");
        verify(findTool(overview, "sakai.synoptic.announcement")).setLayoutHints("0,1");
        verify(findTool(overview, "sakai.summary.calendar")).setLayoutHints("1,1");
        assertEquals("sakai.lessonbuildertool", pages.get(2).getTools().get(0).getToolId());
        assertSame(originalAssignment, findTool(pages.get(9), "sakai.assignment.grades"));
        assertSame(custom, pages.get(pages.size() - 1));
        assertEquals(17, pages.size());
        List<String> expected = List.of("sakai.syllabus", "sakai.lessonbuildertool", "sakai.schedule",
            "sakai.announcements", "sakai.resources", "sakai.conversations", "sakai.poll", "sakai.forums",
            "sakai.assignment.grades", "sakai.samigo", "sakai.gradebookng", "sakai.dropbox",
            "sakai.mailtool", "sakai.site.roster2", "sakai.siteinfo");
        for (int i = 0; i < expected.size(); i++) {
            assertEquals(expected.get(i), pages.get(i + 1).getTools().get(0).getToolId());
        }
        StandardCourseLayout.apply(site, tools);
        assertEquals(17, pages.size());
        assertEquals(3, overview.getTools().size());
        verify(site, never()).removePage(any());
    }

    @Test
    public void missingToolFailsBeforeMutatingSite() {
        when(tools.getTool("sakai.lessonbuildertool")).thenReturn(null);
        assertThrows(IllegalStateException.class, () -> StandardCourseLayout.apply(site, tools));
        verify(site, never()).addPage();
        assertTrue(pages.isEmpty());
    }

    @Test
    public void grantChangesOnlyStudentVisibleRosterPermissionAndIsIdempotent() throws Exception {
        AuthzGroupService service = mock(AuthzGroupService.class);
        AuthzGroup realm = mock(AuthzGroup.class);
        Role student = mock(Role.class);
        when(service.getAuthzGroup("/site/fixture-a")).thenReturn(realm);
        when(realm.getRole("Student")).thenReturn(student);
        when(student.isAllowed("roster.viewallmembers")).thenReturn(false, true);
        StandardCourseRosterPermissions.ensureStudentAccess(service, "/site/fixture-a");
        StandardCourseRosterPermissions.ensureStudentAccess(service, "/site/fixture-a");
        verify(student).allowFunction("roster.viewallmembers");
        verify(student, times(2)).isAllowed("roster.viewallmembers");
        verifyNoMoreInteractions(student);
        verify(service).save(realm);
        verify(realm, never()).getRole("Instructor");
        verify(realm, never()).addMember(anyString(), anyString(), anyBoolean(), anyBoolean());
    }

    @Test
    public void missingStudentRoleFailsWithoutSavingRealm() throws Exception {
        AuthzGroupService service = mock(AuthzGroupService.class);
        AuthzGroup realm = mock(AuthzGroup.class);
        when(service.getAuthzGroup("!site.template.course")).thenReturn(realm);
        assertThrows(IllegalStateException.class,
            () -> StandardCourseRosterPermissions.ensureStudentAccess(service, "!site.template.course"));
        verify(service, never()).save(any());
    }

    @Test
    public void migrationRepairsPermissionEvenWhenLayoutVersionAlreadyCurrent() throws Exception {
        siteProperties.addProperty(StandardCourseLayout.VERSION_PROPERTY, "2");
        AuthzGroupService realms = mock(AuthzGroupService.class);
        Role templateStudent = realm(realms, "!site.template.course", true);
        Role courseStudent = realm(realms, "/site/fixture-a", false);
        SiteService sites = mock(SiteService.class);
        when(sites.getSite("fixture-a")).thenReturn(site);
        StandardCourseLayoutMigrationJob job = job(sites, realms, "fixture-a");
        job.execute(null);
        verify(courseStudent).allowFunction("roster.viewallmembers");
        verify(templateStudent, never()).allowFunction(anyString());
        verify(site, never()).addPage();
        verify(sites, never()).save(any());
    }

    @Test
    public void migrationUpgradesLegacyMarkerOnceAndConfiguresCourseTemplate() throws Exception {
        siteProperties.addProperty("sakai.course.layout.standard.migrated", "true");
        AuthzGroupService realms = mock(AuthzGroupService.class);
        Role templateStudent = realm(realms, "!site.template.course", false);
        Role courseStudent = realm(realms, "/site/fixture-a", false);
        SiteService sites = mock(SiteService.class);
        when(sites.getSite("fixture-a")).thenReturn(site);
        StandardCourseLayoutMigrationJob job = job(sites, realms, "fixture-a");
        job.execute(null);
        job.execute(null);
        assertEquals("2", siteProperties.getProperty(StandardCourseLayout.VERSION_PROPERTY));
        assertEquals(16, pages.size());
        verify(sites).save(site);
        verify(templateStudent).allowFunction("roster.viewallmembers");
        verify(courseStudent).allowFunction("roster.viewallmembers");
        verify(realms, times(2)).save(any());
    }

    @Test
    public void missingTemplateFailsBeforeTouchingCourse() throws Exception {
        AuthzGroupService realms = mock(AuthzGroupService.class);
        AuthzGroup template = mock(AuthzGroup.class);
        when(realms.getAuthzGroup("!site.template.course")).thenReturn(template);
        SiteService sites = mock(SiteService.class);
        StandardCourseLayoutMigrationJob job = job(sites, realms, "fixture-a");
        assertThrows(JobExecutionException.class, () -> job.execute(null));
        verifyNoInteractions(sites);
        verify(realms, never()).save(any());
    }

    @Test
    public void migrationRefusesSpecialSiteAndLeavesItsRealmUntouched() throws Exception {
        when(site.getId()).thenReturn("!admin");
        AuthzGroupService realms = mock(AuthzGroupService.class);
        realm(realms, "!site.template.course", true);
        SiteService sites = mock(SiteService.class);
        when(sites.getSite("!admin")).thenReturn(site);
        job(sites, realms, "!admin").execute(null);
        verify(realms, never()).getAuthzGroup("/site/fixture-a");
        verify(sites, never()).save(any());
    }

    @Test
    public void unconfiguredJobDoesNotTouchCourseTemplate() throws Exception {
        AuthzGroupService realms = mock(AuthzGroupService.class);
        SiteService sites = mock(SiteService.class);
        job(sites, realms).execute(null);
        verifyNoInteractions(realms, sites);
    }

    private StandardCourseLayoutMigrationJob job(SiteService sites, AuthzGroupService realms, String... ids) {
        StandardCourseLayoutMigrationJob job = new StandardCourseLayoutMigrationJob();
        ServerConfigurationService config = mock(ServerConfigurationService.class);
        when(config.getStrings("course.site.layout.migration.siteids")).thenReturn(ids);
        job.setServerConfigurationService(config);
        job.setToolManager(tools);
        job.setSecurityService(mock(SecurityService.class));
        job.setAuthzGroupService(realms);
        job.setSiteService(sites);
        return job;
    }

    private Role realm(AuthzGroupService service, String id, boolean allowed) throws Exception {
        AuthzGroup group = mock(AuthzGroup.class);
        Role student = mock(Role.class);
        when(service.getAuthzGroup(id)).thenReturn(group);
        when(group.getRole("Student")).thenReturn(student);
        when(student.isAllowed("roster.viewallmembers")).thenReturn(allowed, true);
        return student;
    }

    private ResourcePropertiesEdit properties() {
        ResourcePropertiesEdit props = mock(ResourcePropertiesEdit.class);
        Map<String, String> values = new HashMap<>();
        doAnswer(i -> { values.put(i.getArgument(0), i.getArgument(1)); return null; })
            .when(props).addProperty(anyString(), anyString());
        when(props.getProperty(anyString())).thenAnswer(i -> values.get(i.getArgument(0)));
        return props;
    }

    private SitePage page() {
        SitePage page = mock(SitePage.class);
        List<ToolConfiguration> configurations = new ArrayList<>();
        ResourcePropertiesEdit props = properties();
        when(page.getPropertiesEdit()).thenReturn(props);
        when(page.isHomePage()).thenAnswer(i -> "true".equals(props.getProperty(SitePage.IS_HOME_PAGE)));
        when(page.getTools()).thenReturn(configurations);
        when(page.addTool()).thenAnswer(i -> {
            ToolConfiguration tool = mock(ToolConfiguration.class);
            AtomicReference<String> id = new AtomicReference<>();
            doAnswer(call -> { id.set(call.getArgument(0)); return null; }).when(tool).setTool(anyString(), any());
            when(tool.getToolId()).thenAnswer(call -> id.get());
            configurations.add(tool);
            return tool;
        });
        doAnswer(i -> {
            int index = pages.indexOf(page);
            pages.remove(index);
            pages.add(index - 1, page);
            return null;
        }).when(page).moveUp();
        pages.add(page);
        return page;
    }

    private ToolConfiguration findTool(SitePage page, String id) {
        return page.getTools().stream().filter(t -> id.equals(t.getToolId())).findFirst().orElseThrow();
    }
}
