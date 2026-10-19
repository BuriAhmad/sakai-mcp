/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.webapi.mcp.announcements;

import static org.junit.Assert.assertThrows;
import org.junit.Test;

/** Source and packaged-class retirement; replacement contract cases live in Python. */
public class McpAnnouncementWriteControllerTest {
    @Test
    public void retiredControllerIsAbsent() {
        assertThrows(ClassNotFoundException.class,
                () -> Class.forName("org.sakaiproject.webapi.mcp.announcements.McpAnnouncementWriteController"));
    }
}
