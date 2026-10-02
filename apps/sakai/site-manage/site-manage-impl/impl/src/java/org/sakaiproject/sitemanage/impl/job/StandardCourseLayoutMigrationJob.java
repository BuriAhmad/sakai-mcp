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
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.quartz.Job;
import org.quartz.JobExecutionContext;
import org.quartz.JobExecutionException;
import org.sakaiproject.authz.api.AuthzGroupService;
import org.sakaiproject.authz.api.SecurityAdvisor;
import org.sakaiproject.authz.api.SecurityService;
import org.sakaiproject.component.api.ServerConfigurationService;
import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SiteService;
import org.sakaiproject.tool.api.ToolManager;

import lombok.Setter;
import lombok.extern.slf4j.Slf4j;

/**
 * One-time, site-service migration for existing course sites. The marker is
 * stored as a versioned site property. The v2 upgrade adds Lessons and corrects
 * Overview without deleting content. Student roster grants are checked independently.
 */
@Slf4j
public class StandardCourseLayoutMigrationJob implements Job {

    private static final List<String> REQUIRED_TOOL_IDS = StandardCourseLayout.requiredToolIds();

    @Setter private SiteService siteService;
    @Setter private SecurityService securityService;
    @Setter private AuthzGroupService authzGroupService;
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
            try {
                StandardCourseRosterPermissions.ensureStudentAccess(authzGroupService, "!site.template.course");
                log.info("Standard course Student roster permission ready for realm !site.template.course");
            } catch (Exception e) {
                log.error("Could not configure standard course Student roster template", e);
                throw new JobExecutionException("Course Student roster template setup failed", e);
            }
            for (String siteId : requestedIds) {
                try {
                    Site site = siteService.getSite(siteId);
                    if (!"course".equals(site.getType()) || siteId.startsWith("!")
                            || "true".equalsIgnoreCase(site.getProperties().getProperty("template"))) {
                        throw new IllegalArgumentException("Refusing non-course, special, or template site " + siteId);
                    }
                    // Permission state is checked independently of the navigation version.
                    StandardCourseRosterPermissions.ensureStudentAccess(authzGroupService, site.getReference());
                    if (!StandardCourseLayout.VERSION.equals(
                            site.getProperties().getProperty(StandardCourseLayout.VERSION_PROPERTY))) {
                        StandardCourseLayout.apply(site, toolManager);
                        site.getPropertiesEdit().addProperty(StandardCourseLayout.VERSION_PROPERTY, StandardCourseLayout.VERSION);
                        siteService.save(site);
                    }
                    log.info("Standard course setup v2 complete for site {}", siteId);
                } catch (Exception e) {
                    log.error("Could not apply standard course setup v2 for site {}", siteId, e);
                }
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

}
