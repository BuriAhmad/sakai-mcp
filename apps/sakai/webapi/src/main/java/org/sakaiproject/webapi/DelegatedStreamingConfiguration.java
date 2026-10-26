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
package org.sakaiproject.webapi;

import org.sakaiproject.mcpauth.DelegatedCredentialGuard;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.MethodParameter;
import org.springframework.http.ResponseEntity;
import org.springframework.http.server.ServletServerHttpResponse;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodReturnValueHandler;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBodyReturnValueHandler;

import java.util.stream.Collectors;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/** Keeps existing delegated artifact streams inside the authenticated native request lifetime. */
@Configuration(proxyBeanMethods = false)
public class DelegatedStreamingConfiguration {
    @Bean
    public static BeanPostProcessor delegatedArtifactStreaming() {
        return new BeanPostProcessor() {
            @Override
            public Object postProcessAfterInitialization(Object bean, String name) {
                if (bean instanceof RequestMappingHandlerAdapter adapter
                        && adapter.getReturnValueHandlers() != null) {
                    adapter.setReturnValueHandlers(
                            adapter.getReturnValueHandlers().stream()
                                    .map(
                                            handler ->
                                                    handler
                                                                    instanceof
                                                                    StreamingResponseBodyReturnValueHandler
                                                            ? new SynchronousArtifact(handler)
                                                            : handler)
                                    .collect(Collectors.toList()));
                }
                return bean;
            }
        };
    }

    private static final class SynchronousArtifact implements HandlerMethodReturnValueHandler {
        private final HandlerMethodReturnValueHandler original;

        SynchronousArtifact(HandlerMethodReturnValueHandler original) {
            this.original = original;
        }

        @Override
        public boolean supportsReturnType(MethodParameter type) {
            return original.supportsReturnType(type);
        }

        @Override
        public void handleReturnValue(
                Object value,
                MethodParameter type,
                ModelAndViewContainer model,
                NativeWebRequest web)
                throws Exception {
            HttpServletRequest request = web.getNativeRequest(HttpServletRequest.class);
            if (request == null || !DelegatedCredentialGuard.isDelegatedArtifactRequest(request)) {
                original.handleReturnValue(value, type, model, web);
                return;
            }
            HttpServletResponse response = web.getNativeResponse(HttpServletResponse.class);
            if (response == null) {
                throw new IllegalStateException("Missing delegated response");
            }
            model.setRequestHandled(true);
            ServletServerHttpResponse output = new ServletServerHttpResponse(response);
            if (value instanceof ResponseEntity<?> entity) {
                response.setStatus(entity.getStatusCodeValue());
                output.getHeaders().putAll(entity.getHeaders());
                value = entity.getBody();
            }
            if (value != null) {
                ((StreamingResponseBody) value).writeTo(output.getBody());
            }
            output.flush();
        }
    }
}
