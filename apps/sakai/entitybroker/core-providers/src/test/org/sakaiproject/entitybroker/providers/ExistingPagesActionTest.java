/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.entitybroker.providers;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import org.junit.Test;
import org.sakaiproject.authz.api.Member;
import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.entitybroker.DeveloperHelperService;
import org.sakaiproject.entitybroker.EntityView;
import org.sakaiproject.entitybroker.entityprovider.extension.ActionReturn;
import org.sakaiproject.entitybroker.entityprovider.search.Search;
import org.sakaiproject.site.api.*;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.*;

import java.lang.reflect.Field;
import java.util.*;

/** Existing provider behavior only; no new native handler or permission grant. */
public class ExistingPagesActionTest {
    @Test
    public void memberPagesExposeExactRelationsAndRawActionReturn() throws Exception {
        SiteEntityProvider provider = new SiteEntityProvider();
        SiteService sites = mock(SiteService.class);
        Site site = mock(Site.class);
        Member member = mock(Member.class);
        DeveloperHelperService helper = mock(DeveloperHelperService.class);
        ToolManager tools = mock(ToolManager.class);
        ThreadLocalManager threads = mock(ThreadLocalManager.class);
        org.sakaiproject.component.api.ComponentManager manager =
                mock(org.sakaiproject.component.api.ComponentManager.class);
        provider.setSiteService(sites);
        provider.setDeveloperHelperService(helper);
        provider.setThreadLocalManager(threads);
        when(helper.getCurrentUserId()).thenReturn("uid-a");
        when(helper.getCurrentUserReference()).thenReturn("/user/uid-a");
        when(sites.getSite("course-a")).thenReturn(site);
        when(site.getId()).thenReturn("course-a");
        when(site.getMember("uid-a")).thenReturn(member);
        when(member.isActive()).thenReturn(true);
        ResourceProperties props = mock(ResourceProperties.class);
        when(props.getPropertyNames()).thenAnswer(i -> Collections.emptyIterator());
        when(site.getProperties()).thenReturn(props);
        SitePage page = mock(SitePage.class);
        when(page.getId()).thenReturn("page-a");
        when(page.getSiteId()).thenReturn("course-a");
        when(page.getUrl())
                .thenReturn("https://sakai.example.test/portal/site/course-a/page/page-a");
        ToolConfiguration placement = mock(ToolConfiguration.class);
        Tool tool = mock(Tool.class);
        when(tool.getId()).thenReturn("sakai.announcements");
        when(placement.getTool()).thenReturn(tool);
        when(placement.getToolId()).thenReturn("sakai.announcements");
        when(placement.getId()).thenReturn("placement-a");
        when(placement.getContext()).thenReturn("course-a");
        when(placement.getSiteId()).thenReturn("course-a");
        when(placement.getPageId()).thenReturn("page-a");
        when(placement.getConfig()).thenReturn(new Properties());
        when(page.getTools()).thenReturn(List.of(placement));
        when(site.getOrderedPages()).thenReturn(List.of(page));
        when(tools.allowTool(site, placement)).thenReturn(true);
        when(manager.get(DeveloperHelperService.class)).thenReturn(helper);
        when(manager.get(ToolManager.class.getName())).thenReturn(tools);
        Field component = ComponentManager.class.getDeclaredField("m_componentManager");
        component.setAccessible(true);
        Object previous = component.get(null);
        try {
            component.set(null, manager);
            ActionReturn result =
                    provider.getPagesAndTools(
                            new EntityView("/site/course-a/pages.json"), new Search());
            Object data = result.entityData.getData();
            assertTrue(data instanceof List);
            Map<?, ?> row = (Map<?, ?>) ((List<?>) data).get(0);
            Map<?, ?> found = (Map<?, ?>) ((List<?>) row.get("tools")).get(0);
            assertEquals("course-a", row.get("siteId"));
            assertEquals("placement-a", found.get("placementId"));
            assertEquals("sakai.announcements", found.get("toolId"));
            assertEquals("course-a", found.get("context"));
            assertEquals("page-a", found.get("pageId"));
            assertEquals(row.get("url"), found.get("url"));
            assertFalse(found.containsKey("config"));
            // Page visibility remains controlled by the unchanged native ToolManager.
            when(tools.allowTool(site, placement)).thenReturn(false);
            assertTrue(
                    ((List<?>)
                                    provider.getPagesAndTools(
                                                    new EntityView("/site/course-a/pages.json"),
                                                    new Search())
                                            .entityData
                                            .getData())
                            .isEmpty());
            when(member.isActive()).thenReturn(false);
            assertThrows(
                    SecurityException.class,
                    () ->
                            provider.getPagesAndTools(
                                    new EntityView("/site/course-a/pages.json"), new Search()));
        } finally {
            component.set(null, previous);
        }
    }

    @Test
    public void anonymousCannotReadPagesBeforeSiteLookup() {
        SiteEntityProvider provider = new SiteEntityProvider();
        DeveloperHelperService helper = mock(DeveloperHelperService.class);
        SiteService sites = mock(SiteService.class);
        provider.setDeveloperHelperService(helper);
        provider.setSiteService(sites);
        assertThrows(
                SecurityException.class,
                () ->
                        provider.getPagesAndTools(
                                new EntityView("/site/course-a/pages.json"), new Search()));
        verifyNoInteractions(sites);
    }

    @Test
    public void explicitAccessCollectionDoesNotBecomeAnySelectionForAdmin() {
        SiteEntityProvider provider = new SiteEntityProvider();
        SiteService sites = mock(SiteService.class);
        DeveloperHelperService helper = mock(DeveloperHelperService.class);
        provider.setSiteService(sites);
        provider.setDeveloperHelperService(helper);
        when(helper.getCurrentUserId()).thenReturn("uid-a");
        when(helper.getCurrentUserReference()).thenReturn("/user/uid-a");
        when(helper.isUserAdmin("/user/uid-a")).thenReturn(true);
        Search search = new Search();
        search.addRestriction(
                new org.sakaiproject.entitybroker.entityprovider.search.Restriction(
                        "select", "access"));
        assertTrue(
                provider.getEntities(
                                new org.sakaiproject.entitybroker.EntityReference("/site"), search)
                        .isEmpty());
        verify(sites)
                .getSites(
                        eq(SiteService.SelectionType.ACCESS),
                        isNull(),
                        isNull(),
                        isNull(),
                        eq(SiteService.SortType.TITLE_ASC),
                        any(org.sakaiproject.javax.PagingPosition.class));
    }
}
