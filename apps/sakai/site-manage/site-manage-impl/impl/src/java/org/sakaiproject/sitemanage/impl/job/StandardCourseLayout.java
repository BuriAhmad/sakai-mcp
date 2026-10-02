/*
 * Copyright (c) 2026 The Apereo Foundation
 * Licensed under the Educational Community License, Version 2.0.
 * http://www.opensource.org/licenses/ecl2
 */
package org.sakaiproject.sitemanage.impl.job;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.HashSet;
import java.util.Set;

import org.sakaiproject.site.api.Site;
import org.sakaiproject.site.api.SitePage;
import org.sakaiproject.site.api.ToolConfiguration;
import org.sakaiproject.tool.api.Tool;
import org.sakaiproject.tool.api.ToolManager;

/** Shared course layout for fixture creation and the explicit migration. */
final class StandardCourseLayout {
    static final String VERSION = "2";
    static final String VERSION_PROPERTY = "sakai.course.layout.standard.version";
    static final List<String> NAVIGATION_TOOL_IDS = Collections.unmodifiableList(Arrays.asList(
        "sakai.syllabus", "sakai.lessonbuildertool", "sakai.schedule", "sakai.announcements",
        "sakai.resources", "sakai.conversations", "sakai.poll", "sakai.forums",
        "sakai.assignment.grades", "sakai.samigo", "sakai.gradebookng", "sakai.dropbox",
        "sakai.mailtool", "sakai.site.roster2", "sakai.siteinfo"));
    static final List<String> OVERVIEW_TOOL_IDS = Collections.unmodifiableList(Arrays.asList(
        "sakai.iframe.site", "sakai.synoptic.announcement", "sakai.summary.calendar"));

    private StandardCourseLayout() { }

    static List<String> requiredToolIds() {
        List<String> ids = new ArrayList<>(OVERVIEW_TOOL_IDS);
        ids.addAll(NAVIGATION_TOOL_IDS);
        return ids;
    }

    static void apply(Site site, ToolManager toolManager) {
        // Validate before changing even the in-memory site.
        for (String id : requiredToolIds()) {
            if (toolManager.getTool(id) == null) {
                throw new IllegalStateException("Required standard course tool is not registered: " + id);
            }
        }
        SitePage overview = site.getPages().stream().filter(SitePage::isHomePage).findFirst().orElse(null);
        if (overview == null) overview = site.addPage();
        overview.getPropertiesEdit().addProperty(SitePage.IS_HOME_PAGE, "true");
        overview.setLayout(SitePage.LAYOUT_DOUBLE_COL);
        tool(overview, "sakai.iframe.site", toolManager).setLayoutHints("0,0");
        ToolConfiguration announcements = tool(overview, "sakai.synoptic.announcement", toolManager);
        announcements.setTitle("Recent Announcements");
        announcements.setLayoutHints("0,1");
        ToolConfiguration calendar = tool(overview, "sakai.summary.calendar", toolManager);
        calendar.setTitle("Calendar");
        calendar.setLayoutHints("1,1");
        overview.setTitle("Overview");
        moveTo(site, overview, 0);

        Set<SitePage> assigned = new HashSet<>();
        assigned.add(overview);
        int index = 1;
        for (String id : NAVIGATION_TOOL_IDS) {
            SitePage page = site.getPages().stream()
                .filter(p -> !assigned.contains(p))
                .filter(p -> p.getTools().stream().anyMatch(t -> id.equals(t.getToolId())))
                .findFirst().orElse(null);
            if (page == null) {
                page = site.addPage();
                tool(page, id, toolManager).setLayoutHints("0,0");
            }
            page.setTitle(toolManager.getTool(id).getTitle());
            moveTo(site, page, index++);
            assigned.add(page);
        }
        // Preserve additional/custom pages and all existing tool placements and content.
    }

    private static void moveTo(Site site, SitePage page, int index) {
        while (site.getPages().indexOf(page) > index) page.moveUp();
    }

    private static ToolConfiguration tool(SitePage page, String id, ToolManager toolManager) {
        for (ToolConfiguration existing : page.getTools()) {
            if (id.equals(existing.getToolId())) return existing;
        }
        Tool registration = toolManager.getTool(id);
        ToolConfiguration added = page.addTool();
        added.setTool(id, registration);
        added.setTitle(registration.getTitle());
        return added;
    }
}
