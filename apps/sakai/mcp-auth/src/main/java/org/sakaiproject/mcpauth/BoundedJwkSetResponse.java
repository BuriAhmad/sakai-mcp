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

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.ClientHttpResponse;

import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;

/** Bounds actual JWKS response bytes, including responses without Content-Length. */
final class BoundedJwkSetResponse implements ClientHttpResponse {
    private static final int MAX_BODY_BYTES = 1_000_000;
    private final ClientHttpResponse delegate;
    private InputStream body;

    BoundedJwkSetResponse(ClientHttpResponse delegate) {
        this.delegate = delegate;
    }

    @Override
    public HttpStatus getStatusCode() throws IOException {
        return delegate.getStatusCode();
    }

    @Override
    public int getRawStatusCode() throws IOException {
        return delegate.getRawStatusCode();
    }

    @Override
    public String getStatusText() throws IOException {
        return delegate.getStatusText();
    }

    @Override
    public HttpHeaders getHeaders() {
        return delegate.getHeaders();
    }

    @Override
    public void close() {
        delegate.close();
    }

    @Override
    public InputStream getBody() throws IOException {
        if (body == null) {
            body = new BoundedInputStream(delegate.getBody());
        }
        return body;
    }

    private static final class BoundedInputStream extends FilterInputStream {
        private int remaining = MAX_BODY_BYTES;

        BoundedInputStream(InputStream input) {
            super(input);
        }

        @Override
        public int read() throws IOException {
            int value = in.read();
            if (value != -1 && --remaining < 0) {
                throw new IOException("Key response limit");
            }
            return value;
        }

        @Override
        public int read(byte[] bytes, int offset, int length) throws IOException {
            int count = in.read(bytes, offset, Math.min(length, Math.max(1, remaining + 1)));
            if (count > 0 && (remaining -= count) < 0) {
                throw new IOException("Key response limit");
            }
            return count;
        }
    }
}
