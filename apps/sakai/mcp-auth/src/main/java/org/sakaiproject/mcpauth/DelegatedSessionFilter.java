/*
 * Copyright (c) 2026 The Apereo Foundation
 *
 * Licensed under the Educational Community License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *             http://opensource.org/licenses/ecl2
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.sakaiproject.mcpauth;

import org.sakaiproject.component.cover.ComponentManager;
import org.sakaiproject.thread_local.api.ThreadLocalManager;
import org.sakaiproject.tool.api.SessionManager;
import org.sakaiproject.util.RequestFilter;

import java.io.IOException;
import java.security.Principal;

import javax.servlet.DispatcherType;
import javax.servlet.Filter;
import javax.servlet.FilterChain;
import javax.servlet.FilterConfig;
import javax.servlet.ServletException;
import javax.servlet.ServletRequest;
import javax.servlet.ServletResponse;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletRequestWrapper;
import javax.servlet.http.HttpServletResponse;

/** Runs after native request/auth infrastructure, before the unchanged handler. */
public final class DelegatedSessionFilter implements Filter {
    private SessionManager sessions;
    private ThreadLocalManager threads;

    public DelegatedSessionFilter() {}

    DelegatedSessionFilter(SessionManager sessions, ThreadLocalManager threads) {
        this.sessions = sessions;
        this.threads = threads;
    }

    @Override
    public void init(FilterConfig config) {
        if (sessions == null) {
            sessions = ComponentManager.get(SessionManager.class);
            threads = ComponentManager.get(ThreadLocalManager.class);
        }
    }

    @Override
    public void doFilter(ServletRequest raw, ServletResponse output, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest request = (HttpServletRequest) raw;
        Object marker = request.getAttribute(DelegatedCredentialGuard.MARKER);
        if (marker == null) {
            chain.doFilter(raw, output);
            return;
        }
        if (!(marker instanceof DelegatedCredentialGuard.BoundIdentity bound)
                || (request.getDispatcherType() != DispatcherType.REQUEST
                        && !(bound.conversation()
                                && (request.getDispatcherType() == DispatcherType.FORWARD
                                        || request.getDispatcherType() == DispatcherType.INCLUDE)))
                || request.getAttribute(RequestFilter.ATTR_SESSION) != bound.session()
                || sessions.getCurrentSession() != bound.session()
                || !bound.uid().equals(bound.session().getUserId())
                || !bound.eid().equals(bound.session().getUserEid())) {
            ((HttpServletResponse) output).sendError(403);
            return;
        }
        HttpServletRequest aligned =
                new HttpServletRequestWrapper(request) {
                    @Override
                    public String getRemoteUser() {
                        return bound.eid();
                    }

                    @Override
                    public Principal getUserPrincipal() {
                        return () -> bound.uid();
                    }
                };
        Object previous = threads.get(RequestFilter.CURRENT_HTTP_REQUEST);
        try {
            threads.set(RequestFilter.CURRENT_HTTP_REQUEST, aligned);
            chain.doFilter(aligned, output);
        } finally {
            threads.set(RequestFilter.CURRENT_HTTP_REQUEST, previous);
        }
    }
}
