/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.mcpauth;

import static org.mockito.Mockito.*;

import org.junit.Test;
import org.sakaiproject.util.RequestFilter;
import org.sakaiproject.webapi.WebAppConfiguration;

import java.util.EnumSet;

import javax.servlet.*;

public class DelegatedRegistrationTest {
    @Test
    public void actualInitializerRegistersOnlySharedGuardNativeFilterAndBinderInOrder()
            throws Exception {
        var context = mock(ServletContext.class);
        var registration = mock(FilterRegistration.Dynamic.class);
        when(context.addFilter(
                        anyString(), org.mockito.ArgumentMatchers.<Class<? extends Filter>>any()))
                .thenReturn(registration);
        when(context.addServlet(anyString(), any(Servlet.class)))
                .thenReturn(mock(ServletRegistration.Dynamic.class));
        new WebAppConfiguration().onStartup(context);
        var order = inOrder(context);
        order.verify(context)
                .addFilter("sakai.delegated.credentials", DelegatedCredentialGuard.class);
        order.verify(context).addFilter("sakai.request", RequestFilter.class);
        order.verify(context).addFilter("sakai.delegated.session", DelegatedSessionFilter.class);
        verify(context, times(3))
                .addFilter(
                        anyString(), org.mockito.ArgumentMatchers.<Class<? extends Filter>>any());
        verify(context, never()).addFilter(anyString(), any(Filter.class));
        verify(registration, times(2))
                .addMappingForUrlPatterns(EnumSet.of(DispatcherType.REQUEST), true, "/*");
        verify(registration)
                .addMappingForUrlPatterns(
                        EnumSet.of(
                                DispatcherType.REQUEST,
                                DispatcherType.FORWARD,
                                DispatcherType.INCLUDE),
                        true,
                        "/*");
    }
}
