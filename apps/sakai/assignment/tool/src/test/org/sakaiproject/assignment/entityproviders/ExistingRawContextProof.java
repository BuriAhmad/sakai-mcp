/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL-2.0. */
package org.sakaiproject.assignment.entityproviders;

import static org.junit.Assert.*;

import java.time.Instant;
import java.util.Map;
import org.azeckoski.reflectutils.transcoders.JSONTranscoder;
import org.junit.Test;
import org.sakaiproject.assignment.api.model.Assignment;

/** Existing EntityBroker codec/model characterization, not native role acceptance. */
public class ExistingRawContextProof {
    @Test
    public void rawContextPreservesRequiredStateAndPropertyMap() {
        Assignment assignment = new Assignment();
        assignment.setId("assignment-a");
        assignment.setContext("course-a");
        assignment.setTitle("Synthetic context");
        assignment.setScaleFactor(100);
        assignment.setMaxGradePoint(1250);
        assignment.setReleaseGrades(false);
        assignment.setDeleted(false);
        assignment.setTypeOfGrade(Assignment.GradeType.SCORE_GRADE_TYPE);
        assignment.setOpenDate(Instant.parse("2026-10-01T00:00:00Z"));
        assignment.getProperties().put("allow_resubmit_number", "2");
        JSONTranscoder codec = new JSONTranscoder(true, true, false);
        String encoded = codec.encode(Map.of("assignment", assignment,
                "context", "course-a", "assignmentId", "assignment-a"), "assignment", null);
        Map<?, ?> envelope = codec.decode(encoded);
        assertTrue(envelope.get("assignment") instanceof Map);
        Map<?, ?> raw = (Map<?, ?>) envelope.get("assignment");
        assertEquals(100, ((Number) raw.get("scaleFactor")).intValue());
        assertEquals(1250, ((Number) raw.get("maxGradePoint")).intValue());
        assertEquals(false, raw.get("releaseGrades"));
        assertEquals(false, raw.get("deleted"));
        assertTrue(raw.get("properties") instanceof Map);
        assertEquals("2", ((Map<?, ?>) raw.get("properties")).get("allow_resubmit_number"));
        assertNotNull(raw.get("openDate"));
        System.out.println("SYNTHETIC_RAW_CONTEXT=" + encoded);
    }
}
