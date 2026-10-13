/* Copyright (c) 2026 The Apereo Foundation. Licensed under ECL 2.0. */
package org.sakaiproject.assignment.impl;

import static org.junit.Assert.*;
import java.util.UUID;
import org.hibernate.SessionFactory;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.sakaiproject.assignment.api.model.Assignment;
import org.sakaiproject.assignment.api.model.AssignmentSubmission;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.junit4.SpringJUnit4ClassRunner;

/** Real Hibernate transactions prove every native writer participates in version checks. */
@RunWith(SpringJUnit4ClassRunner.class)
@ContextConfiguration(classes = {AssignmentTestConfiguration.class})
public class AssignmentGradingConcurrencyTest {
    @Autowired @Qualifier("org.sakaiproject.springframework.orm.hibernate.GlobalSessionFactory") SessionFactory factory;
    @Test public void staleNativeWriterCannotOverwriteCommittedGrade() {
        String aid=UUID.randomUUID().toString(), sid=UUID.randomUUID().toString();
        try(var session=factory.openSession()) {
            var tx=session.beginTransaction();Assignment a=new Assignment();a.setId(aid);a.setContext("synthetic-course");a.setTitle("Synthetic quiz");a.setAuthor("synthetic-instructor");a.setDateCreated(java.time.Instant.now());session.save(a);
            AssignmentSubmission submission=new AssignmentSubmission();submission.setId(sid);submission.setAssignment(a);session.save(submission);sid=submission.getId();tx.commit();
        }
        try(var stale=factory.openSession();var fresh=factory.openSession()) {
            var staleTx=stale.beginTransaction();var loaded=stale.get(AssignmentSubmission.class,sid);long before=loaded.getLockVersion();
            var freshTx=fresh.beginTransaction();var updated=fresh.get(AssignmentSubmission.class,sid);updated.setGrade("40");freshTx.commit();assertTrue(updated.getLockVersion()>before);
            loaded.setSubmittedText("stale student content");assertThrows(RuntimeException.class,staleTx::commit);
        }
        try(var session=factory.openSession()) {
            var row=session.get(AssignmentSubmission.class,sid);assertEquals("40",row.getGrade());assertNull(row.getSubmittedText());
        }
    }

    @Test public void gradingCollectionsRemainReadableAfterTransactionalLoad() {
        String aid=UUID.randomUUID().toString(), sid=UUID.randomUUID().toString();
        try(var session=factory.openSession()) {
            var tx=session.beginTransaction();Assignment a=new Assignment();a.setId(aid);a.setContext("synthetic-course");a.setTitle("Synthetic quiz");a.setAuthor("synthetic-instructor");a.setDateCreated(java.time.Instant.now());session.save(a);
            AssignmentSubmission submission=new AssignmentSubmission();submission.setId(sid);submission.setAssignment(a);submission.getAttachments().add("/attachment/synthetic.txt");session.save(submission);sid=submission.getId();tx.commit();
        }
        AssignmentSubmission detached;
        try(var session=factory.openSession()) {
            var tx=session.beginTransaction();detached=session.get(AssignmentSubmission.class,sid);
            assertEquals(1,detached.getAttachments().size());
            detached.getProperties().size();detached.getFeedbackAttachments().size();detached.getSubmitters().size();
            tx.commit();
        }
        assertTrue(detached.getAttachments().contains("/attachment/synthetic.txt"));
    }
}
