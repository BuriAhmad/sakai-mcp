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

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Records fixed failure categories without request, identity, exception or credential values. */
final class DelegatedDiagnostics {
    enum Stage {
        LOGGING_POLICY,
        CONFIGURATION,
        TOKEN_SERVICE,
        NATIVE_SESSION,
        HANDLER,
        SESSION_CLEANUP,
        CONTEXT_RESTORE,
        RESPONSE_COMPLETION,
        RESPONSE_POLICY
    }

    private static final Logger LOG = LoggerFactory.getLogger(DelegatedDiagnostics.class);

    static void failure(Stage stage) {
        LOG.warn("Delegated authentication request failed at stage {}", stage);
    }

    private DelegatedDiagnostics() {}
}
