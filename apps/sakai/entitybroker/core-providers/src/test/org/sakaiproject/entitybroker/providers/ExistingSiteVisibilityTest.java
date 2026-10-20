/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.entitybroker.providers;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

import org.azeckoski.reflectutils.transcoders.JSONTranscoder;
import org.junit.Test;
import org.sakaiproject.entity.api.ResourceProperties;
import org.sakaiproject.entitybroker.providers.model.EntitySite;
import org.sakaiproject.site.api.Site;

import java.util.*;

/** Characterizes the unchanged DTO/JSON codec; no replacement native behavior. */
public class ExistingSiteVisibilityTest {
    @Test
    public void acceptedNativeIdProvesPublicationIsUnmaskedForMembers() {
        for (boolean published : List.of(false, true)) {
            Site site = mock(Site.class);
            when(site.getId()).thenReturn("course-a");
            when(site.getType()).thenReturn("course");
            when(site.isPubView()).thenReturn(true);
            when(site.isPublished()).thenReturn(published);
            when(site.isSoftlyDeleted()).thenReturn(true);
            ResourceProperties props = mock(ResourceProperties.class);
            when(props.getPropertyNames()).thenAnswer(i -> Collections.emptyIterator());
            when(site.getProperties()).thenReturn(props);
            for (boolean member : List.of(false, true)) {
                EntitySite entity = new EntitySite(site, false, false, member, false);
                JSONTranscoder codec = new JSONTranscoder(true, true, false);
                String json =
                        codec.encode(
                                entity,
                                "site",
                                Map.of(
                                        "entityId",
                                        "course-a",
                                        "entityReference",
                                        "/site/course-a"));
                Map<?, ?> decoded = codec.decode(json);
                assertEquals(member ? "course-a" : "", decoded.get("id"));
                assertEquals(member && published, decoded.get("published"));
                assertEquals("course-a", decoded.get("entityId"));
                assertEquals(member ? "/site/course-a" : "", decoded.get("reference"));
                // Deletion is a separate mask: an ordinary member's false
                // value is never proof that a site has not been deleted.
                assertEquals(false, decoded.get("softlyDeleted"));
            }
        }
    }
}
