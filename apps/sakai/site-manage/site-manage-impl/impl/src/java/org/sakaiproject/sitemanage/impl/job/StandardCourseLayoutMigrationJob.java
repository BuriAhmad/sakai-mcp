/**
 * Copyright (c) 2026 The Apereo Foundation
 *
 * Licensed under the Educational Community License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License. You may
 * obtain a copy of the License at
 *
 *             http://www.opensource.org/licenses/ecl2
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 */
package org.sakaiproject.sitemanage.impl.job;

import java.util.Arrays;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.quartz.Job;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.sakaiproject.authz.api.SecurityAdvisor;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SitePage;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.site.api.ToolConfiguration;
import org.sakaiproject.tool.api.Tool;
import org.sakaiproject.tool.api.ToolManager;

import lombok.Setter;
import lombok.extern.slf4j.Slf4j;

/**
 * One-time, site-service migration for existing course sites. The marker is
 * stored as a normal site property, so a restart is safe and sites already
 * migrated are not reordered again after an instructor customizes them.
 */
@Slf4j
public class StandardCourseLayoutMigrationJob implements Job {

    private static final String MIGRATED_PROPERTY = "sakai.course.layout.standard.migrated";
    private static final String[] NAVIGATION_TOOL_IDS = {
        "sakai.syllabus", "sakai.schedule", "sakai.announcements", "sakai.resources",
        "sakai.conversations", "sakai.poll", "sakai.forums", "sakai.assignment.grades",
        "sakai.samigo", "sakai.gradebookng", "sakai.dropbox", "sakai.mailtool",
        "sakai.site.roster2", "sakai.siteinfo"
    };
    private static final List<String> OVERVIEW_TOOL_IDS = Arrays.asList(
        "sakai.iframe.site", "sakai.synoptic.announcement", "sakai.summary.calendar");
    private static final List<String> REQUIRED_TOOL_IDS = requiredToolIds();

    @Setter private SiteService siteService;
    @Setter private SecurityService securityService;
    @Setter private ToolManager toolManager;
    @Setter private ServerConfigurationService serverConfigurationService;

    @Override
    public void execute(JobExecutionContext context) throws JobExecutionException {
        String[] configuredIds = serverConfigurationService.getStrings("course.site.layout.migration.siteids");
        Set<String> requestedIds = configuredIds == null ? new HashSet<>() : new HashSet<>(Arrays.asList(configuredIds));
        if (requestedIds.isEmpty()) {
            log.info("No course-site IDs were configured; no sites were changed.");
            return;
        }
        if (!awaitToolRegistrations()) {
            log.error("Required standard course tools did not all register; no course sites were changed.");
            return;
        }
        SecurityAdvisor advisor = (userId, function, reference) -> SecurityAdvisor.SecurityAdvice.ALLOWED;
        securityService.pushAdvisor(advisor);
        try {
            for (Site site : siteService.getSites(SiteService.SelectionType.ANY, null, null, null,
                    SiteService.SortType.TITLE_ASC, null)) {
                if (!requestedIds.remove(site.getId())) continue;
                if (!"course".equals(site.getType()) || site.getId().startsWith("!")
                        || "true".equalsIgnoreCase(site.getProperties().getProperty("template"))) {
                    log.error("Refusing course-layout migration for non-course or template site {}", site.getId());
                    continue;
                }
                if ("true".equalsIgnoreCase(site.getProperties().getProperty(MIGRATED_PROPERTY))) {
                    log.info("Course navigation is already standardized for site {}", site.getId());
                    continue;
                }
                try {
                    migrate(site);
                } catch (Exception e) {
                    log.error("Could not standardize course layout for site {}", site.getId(), e);
                }
            }
            for (String missingId : requestedIds) {
                log.error("Requested course-layout migration site was not found: {}", missingId);
            }
        } finally {
            securityService.popAdvisor(advisor);
        }
    }

    /**
     * Quartz AutoRun fires before Tomcat has necessarily deployed every tool WAR.
     * Wait on this worker thread so the migration never writes a partial layout.
     */
    private boolean awaitToolRegistrations() throws JobExecutionException {
        for (int attempt = 1; attempt <= 90; attempt++) {
            List<String> missing = new ArrayList<>();
            for (String toolId : REQUIRED_TOOL_IDS) {
                if (toolManager.getTool(toolId) == null) missing.add(toolId);
            }
            if (missing.isEmpty()) return true;
            if (attempt == 90) {
                log.error("Timed out waiting for required standard course tools to register: {}", missing);
                return false;
            }
            if (attempt == 1 || attempt % 6 == 0) {
                log.info("Waiting for standard course tool registrations: {}", missing);
            }
            try {
                Thread.sleep(10_000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new JobExecutionException("Interrupted while waiting for course tool registrations", e);
            }
        }
        return false;
    }

    private static List<String> requiredToolIds() {
        List<String> toolIds = new ArrayList<>(OVERVIEW_TOOL_IDS);
        toolIds.addAll(Arrays.asList(NAVIGATION_TOOL_IDS));
        return toolIds;
    }

    private void migrate(Site site) throws Exception {
        SitePage overview = findHomePage(site);
        if (overview == null) {
            overview = site.addPage();
        }
        overview.setTitle("Overview");
        overview.getPropertiesEdit().addProperty(SitePage.IS_HOME_PAGE, Boolean.TRUE.toString());

        for (String toolId : OVERVIEW_TOOL_IDS) {
            addToolIfMissing(overview, toolId);
        }
        List<ToolConfiguration> overviewTools = new ArrayList<>(overview.getTools());
        overviewTools.sort(Comparator.comparingInt(tool -> {
            int index = OVERVIEW_TOOL_IDS.indexOf(tool.getToolId());
            return index < 0 ? OVERVIEW_TOOL_IDS.size() : index;
        }));
        for (int i = 0; i < overviewTools.size(); i++) {
            overviewTools.get(i).setLayoutHints("0," + i);
        }
        overview.setTools(overviewTools);

        int desiredIndex = 0;
        for (String toolId : NAVIGATION_TOOL_IDS) {
            SitePage page = findPage(site, toolId);
            if (page == null) {
                page = site.addPage();
                addToolIfMissing(page, toolId);
            }
            Tool registration = toolManager.getTool(toolId);
            if (registration == null) {
                throw new IllegalStateException("Required standard course tool is not registered: " + toolId);
            }
            page.setTitle(registration.getTitle() != null ? registration.getTitle() : toolId);
            while (site.getPages().indexOf(page) > desiredIndex) {
                page.moveUp();
            }
            desiredIndex++;
        }

        // Keep the Overview container first, even if it was added to a legacy site.
        while (site.getPages().indexOf(overview) > 0) {
            overview.moveUp();
        }
        for (SitePage page : new ArrayList<>(site.getPages())) {
            if (page.isHomePage() || containsRequestedTool(page)) continue;
            // Remove only the unrequested navigation placement. Tool records and content stay intact.
            site.removePage(page);
        }
        site.getPropertiesEdit().addProperty(MIGRATED_PROPERTY, Boolean.TRUE.toString());
        siteService.save(site);
        log.info("Standardized course navigation for site {}", site.getId());
    }

    private SitePage findHomePage(Site site) {
        for (SitePage page : site.getPages()) {
            if (page.isHomePage()) return page;
        }
        return null;
    }

    private SitePage findPage(Site site, String toolId) {
        for (SitePage page : site.getPages()) {
            for (ToolConfiguration configuration : page.getTools()) {
                if (toolId.equals(configuration.getToolId())) return page;
            }
        }
        return null;
    }

    private boolean containsRequestedTool(SitePage page) {
        for (ToolConfiguration configuration : page.getTools()) {
            if (Arrays.asList(NAVIGATION_TOOL_IDS).contains(configuration.getToolId())) return true;
        }
        return false;
    }

    private void addToolIfMissing(SitePage page, String toolId) {
        for (ToolConfiguration configuration : page.getTools()) {
            if (toolId.equals(configuration.getToolId())) return;
        }
        Tool registration = toolManager.getTool(toolId);
        if (registration == null) {
            throw new IllegalStateException("Required standard course tool is not registered: " + toolId);
        }
        ToolConfiguration configuration = page.addTool();
        configuration.setTool(toolId, registration);
        configuration.setTitle(registration.getTitle() != null ? registration.getTitle() : toolId);
        if (page.getTools().size() == 1) {
            page.setTitle(registration.getTitle() != null ? registration.getTitle() : toolId);
        }
    }
}
