##
# Copyright (c) 2005-2012 Apple Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##


from calendarserver.tap.util import getRootResource
from calendarserver.tools.purge import PurgePrincipalService

from twistedcaldav.config import config
from twistedcaldav.ical import Component
from twistedcaldav.test.util import TestCase

from pycalendar.datetime import PyCalendarDateTime
from pycalendar.timezone import PyCalendarTimezone

from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks
from txdav.common.datastore.test.util import buildStore, populateCalendarsFrom, CommonCommonTests
from txdav.common.datastore.sql_tables import _BIND_MODE_WRITE

from twext.web2.http_headers import MimeType

import os


future = PyCalendarDateTime.getNowUTC()
future.offsetDay(1)
future = future.getText()

past = PyCalendarDateTime.getNowUTC()
past.offsetDay(-1)
past = past.getText()

# For test_purgeExistingGUID

# No organizer/attendee
NON_INVITE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:151AFC76-6036-40EF-952B-97D1840760BF
SUMMARY:Non Invitation
DTSTART:%s
DURATION:PT1H
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (past,)

# Purging existing organizer; has existing attendee
ORGANIZER_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:7ED97931-9A19-4596-9D4D-52B36D6AB803
SUMMARY:Organizer
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:E9E78C86-4829-4520-A35D-70DDADAB2092
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:E9E78C86-4829-4520-A35D-70DDADAB2092
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)

# Purging existing attendee; has existing organizer
ATTENDEE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1974603C-B2C0-4623-92A0-2436DEAB07EF
SUMMARY:Attendee
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:E9E78C86-4829-4520-A35D-70DDADAB2092
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)


# For test_purgeNonExistentGUID

# No organizer/attendee, in the past
NON_INVITE_PAST_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:151AFC76-6036-40EF-952B-97D1840760BF
SUMMARY:Non Invitation
DTSTART:%s
DURATION:PT1H
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (past,)

# No organizer/attendee, in the future
NON_INVITE_FUTURE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:251AFC76-6036-40EF-952B-97D1840760BF
SUMMARY:Non Invitation
DTSTART:%s
DURATION:PT1H
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)


# Purging non-existent organizer; has existing attendee
ORGANIZER_ICS_2 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:7ED97931-9A19-4596-9D4D-52B36D6AB803
SUMMARY:Organizer
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:1CB4378B-DD76-462D-B4D4-BD131FE89243
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:1CB4378B-DD76-462D-B4D4-BD131FE89243
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)

# Purging non-existent attendee; has existing organizer
ATTENDEE_ICS_2 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1974603C-B2C0-4623-92A0-2436DEAB07EF
SUMMARY:Attendee
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:1CB4378B-DD76-462D-B4D4-BD131FE89243
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)

# Purging non-existent organizer; has existing attendee; repeating
REPEATING_ORGANIZER_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:8ED97931-9A19-4596-9D4D-52B36D6AB803
SUMMARY:Repeating Organizer
DTSTART:%s
DURATION:PT1H
RRULE:FREQ=DAILY;COUNT=400
ORGANIZER:urn:uuid:1CB4378B-DD76-462D-B4D4-BD131FE89243
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:1CB4378B-DD76-462D-B4D4-BD131FE89243
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (past,)


# For test_purgeMultipleNonExistentGUIDs

# No organizer/attendee
NON_INVITE_ICS_3 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:151AFC76-6036-40EF-952B-97D1840760BF
SUMMARY:Non Invitation
DTSTART:%s
DURATION:PT1H
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (past,)

# Purging non-existent organizer; has non-existent and existent attendees
ORGANIZER_ICS_3 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:7ED97931-9A19-4596-9D4D-52B36D6AB803
SUMMARY:Organizer
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:767F9EB0-8A58-4F61-8163-4BE0BB72B873
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:767F9EB0-8A58-4F61-8163-4BE0BB72B873
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:42EB074A-F859-4E8F-A4D0-7F0ADCB73D87
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)

# Purging non-existent attendee; has non-existent organizer and existent attendee
# (Note: Implicit scheduling doesn't update this at all for the existing attendee)
ATTENDEE_ICS_3 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1974603C-B2C0-4623-92A0-2436DEAB07EF
SUMMARY:Attendee
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:42EB074A-F859-4E8F-A4D0-7F0ADCB73D87
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:767F9EB0-8A58-4F61-8163-4BE0BB72B873
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:42EB074A-F859-4E8F-A4D0-7F0ADCB73D87
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)

# Purging non-existent attendee; has non-existent attendee and existent organizer
ATTENDEE_ICS_4 = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:79F26B10-6ECE-465E-9478-53F2A9FCAFEE
SUMMARY:2 non-existent attendees
DTSTART:%s
DURATION:PT1H
ORGANIZER:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:291C2C29-B663-4342-8EA1-A055E6A04D65
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:767F9EB0-8A58-4F61-8163-4BE0BB72B873
ATTENDEE;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:42EB074A-F859-4E8F-A4D0-7F0ADCB73D87
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n") % (future,)



class CancelEventTestCase(TestCase):

    def test_cancelRepeating(self):
        # A repeating event where purged CUA is organizer
        event = Component.fromString(REPEATING_1_ICS_BEFORE)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_MODIFIED)
        self.assertEquals(str(event), REPEATING_1_ICS_AFTER)


    def test_cancelAllDayRepeating(self):
        # A repeating All Day event where purged CUA is organizer
        event = Component.fromString(REPEATING_2_ICS_BEFORE)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_MODIFIED)
        self.assertEquals(str(event), REPEATING_2_ICS_AFTER)


    def test_cancelFutureEvent(self):
        # A future event
        event = Component.fromString(FUTURE_EVENT_ICS)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_SHOULD_DELETE)


    def test_cancelNonMeeting(self):
        # A repeating non-meeting event
        event = Component.fromString(REPEATING_NON_MEETING_ICS)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_SHOULD_DELETE)


    def test_cancelAsAttendee(self):
        # A repeating meeting event where purged CUA is an attendee
        event = Component.fromString(REPEATING_ATTENDEE_MEETING_ICS)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_SHOULD_DELETE)


    def test_cancelAsAttendeeOccurrence(self):
        # A repeating meeting occurrence with no master, where purged CUA is
        # an attendee
        event = Component.fromString(INVITED_TO_OCCURRENCE_ICS)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:9DC04A71-E6DD-11DF-9492-0800200C9A66")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_SHOULD_DELETE)


    def test_cancelAsAttendeeMultipleOccurrences(self):
        # Multiple meeting occurrences with no master, where purged CUA is
        # an attendee
        event = Component.fromString(INVITED_TO_MULTIPLE_OCCURRENCES_ICS)
        action = PurgePrincipalService._cancelEvent(event, PyCalendarDateTime(2010, 12, 6, 12, 0, 0, PyCalendarTimezone(utc=True)),
            "urn:uuid:9DC04A71-E6DD-11DF-9492-0800200C9A66")
        self.assertEquals(action, PurgePrincipalService.CANCELEVENT_SHOULD_DELETE)

# This event begins on Nov 30, 2010, has two EXDATES (Dec 3 and 9), and has two
# overridden instances (Dec 4 and 11).  The Dec 11 one will be removed since
# the cutoff date for this test is Dec 6.

REPEATING_1_ICS_BEFORE = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:59E260E3-1644-4BDF-BBC6-6130B0C3A520
DTSTART;TZID=US/Pacific:20101130T100000
DTEND;TZID=US/Pacific:20101130T110000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T184815Z
DTSTAMP:20101203T185019Z
EXDATE;TZID=US/Pacific:20101203T100000
EXDATE;TZID=US/Pacific:20101209T100000
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
RRULE:FREQ=DAILY;COUNT=400
SEQUENCE:4
SUMMARY:Repeating 1
TRANSP:OPAQUE
END:VEVENT
BEGIN:VEVENT
UID:59E260E3-1644-4BDF-BBC6-6130B0C3A520
RECURRENCE-ID;TZID=US/Pacific:20101204T100000
DTSTART;TZID=US/Pacific:20101204T120000
DTEND;TZID=US/Pacific:20101204T130000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=2.0:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T184815Z
DTSTAMP:20101203T185027Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:6
SUMMARY:Repeating 1
TRANSP:OPAQUE
END:VEVENT
BEGIN:VEVENT
UID:59E260E3-1644-4BDF-BBC6-6130B0C3A520
RECURRENCE-ID;TZID=US/Pacific:20101211T100000
DTSTART;TZID=US/Pacific:20101211T120000
DTEND;TZID=US/Pacific:20101211T130000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=2.0:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T184815Z
DTSTAMP:20101203T185038Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:6
SUMMARY:Repeating 1
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

REPEATING_1_ICS_AFTER = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:59E260E3-1644-4BDF-BBC6-6130B0C3A520
DTSTART;TZID=US/Pacific:20101130T100000
DTEND;TZID=US/Pacific:20101130T110000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T184815Z
DTSTAMP:20101203T185019Z
EXDATE;TZID=US/Pacific:20101203T100000
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
RRULE:FREQ=DAILY;UNTIL=20101206T120000Z
SEQUENCE:4
SUMMARY:Repeating 1
TRANSP:OPAQUE
END:VEVENT
BEGIN:VEVENT
UID:59E260E3-1644-4BDF-BBC6-6130B0C3A520
RECURRENCE-ID;TZID=US/Pacific:20101204T100000
DTSTART;TZID=US/Pacific:20101204T120000
DTEND;TZID=US/Pacific:20101204T130000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=2.0:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T184815Z
DTSTAMP:20101203T185027Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:6
SUMMARY:Repeating 1
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

# This event is similar to the "Repeating 1" event above except this one is an
# all-day event.

REPEATING_2_ICS_BEFORE = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VEVENT
UID:53BA0EA4-05B1-4E89-BD1E-8397F071FD6A
DTSTART;VALUE=DATE:20101130
DTEND;VALUE=DATE:20101201
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T203510Z
DTSTAMP:20101203T203603Z
EXDATE;VALUE=DATE:20101203
EXDATE;VALUE=DATE:20101209
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
RRULE:FREQ=DAILY;COUNT=400
SEQUENCE:5
SUMMARY:All Day
TRANSP:TRANSPARENT
END:VEVENT
BEGIN:VEVENT
UID:53BA0EA4-05B1-4E89-BD1E-8397F071FD6A
RECURRENCE-ID;VALUE=DATE:20101211
DTSTART;VALUE=DATE:20101211
DTEND;VALUE=DATE:20101212
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
CREATED:20101203T203510Z
DTSTAMP:20101203T203631Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:6
SUMMARY:Modified Title
TRANSP:TRANSPARENT
END:VEVENT
BEGIN:VEVENT
UID:53BA0EA4-05B1-4E89-BD1E-8397F071FD6A
RECURRENCE-ID;VALUE=DATE:20101204
DTSTART;VALUE=DATE:20101204
DTEND;VALUE=DATE:20101205
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T203510Z
DTSTAMP:20101203T203618Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:7
SUMMARY:Modified Title
TRANSP:TRANSPARENT
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

REPEATING_2_ICS_AFTER = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VEVENT
UID:53BA0EA4-05B1-4E89-BD1E-8397F071FD6A
DTSTART;VALUE=DATE:20101130
DTEND;VALUE=DATE:20101201
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T203510Z
DTSTAMP:20101203T203603Z
EXDATE;VALUE=DATE:20101203
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
RRULE:FREQ=DAILY;UNTIL=20101206
SEQUENCE:5
SUMMARY:All Day
TRANSP:TRANSPARENT
END:VEVENT
BEGIN:VEVENT
UID:53BA0EA4-05B1-4E89-BD1E-8397F071FD6A
RECURRENCE-ID;VALUE=DATE:20101204
DTSTART;VALUE=DATE:20101204
DTEND;VALUE=DATE:20101205
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTICI
 PANT;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:0F1684
 77-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T203510Z
DTSTAMP:20101203T203618Z
ORGANIZER;CN=Purge Test:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
SEQUENCE:7
SUMMARY:Modified Title
TRANSP:TRANSPARENT
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")


# This event is on Dec 8 (in the future compared to Dec 6) and should be flagged
# as needing to be deleted

FUTURE_EVENT_ICS = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:97B243D3-D252-4034-AA6D-9AE34E063991
DTSTART;TZID=US/Pacific:20101208T091500
DTEND;TZID=US/Pacific:20101208T101500
CREATED:20101203T172929Z
DTSTAMP:20101203T172932Z
SEQUENCE:2
SUMMARY:Future event single
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

REPEATING_NON_MEETING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//Apple Inc.//iCal 4.0.4//EN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:4E4D0C8C-6546-4777-9BF5-AD629C05E7D5
DTSTART;TZID=US/Pacific:20101130T110000
DTEND;TZID=US/Pacific:20101130T120000
CREATED:20101203T204353Z
DTSTAMP:20101203T204409Z
RRULE:FREQ=DAILY;COUNT=400
SEQUENCE:3
SUMMARY:Repeating non meeting
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

REPEATING_ATTENDEE_MEETING_ICS = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//CALENDARSERVER.ORG//NONSGML Version 1//EN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:111A679F-EF8E-4CA5-9262-7C805E2C184D
DTSTART;TZID=US/Pacific:20101130T120000
DTEND;TZID=US/Pacific:20101130T130000
ATTENDEE;CN=Test User;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:3FF02D2
 B-07A3-4420-8570-7B7C7D07F08A
ATTENDEE;CN=Purge Test;CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED;ROLE=REQ-PARTIC
 IPANT:urn:uuid:0F168477-CF3D-45D3-AE60-9875EA02C4D1
CREATED:20101203T204908Z
DTSTAMP:20101203T204927Z
ORGANIZER;CN=Test User;SCHEDULE-STATUS=1.2:urn:uuid:3FF02D2B-07A3-4420-857
 0-7B7C7D07F08A
RRULE:FREQ=DAILY;COUNT=400
SEQUENCE:4
SUMMARY:As an attendee
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")

INVITED_TO_OCCURRENCE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
METHOD:REQUEST
PRODID:-//CALENDARSERVER.ORG//NONSGML Version 1//EN
BEGIN:VTIMEZONE
TZID:America/Los_Angeles
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:44A391CF-52F5-46B4-B35A-E000E3002084
RECURRENCE-ID;TZID=America/Los_Angeles:20111103T150000
DTSTART;TZID=America/Los_Angeles:20111103T150000
DTEND;TZID=America/Los_Angeles:20111103T170000
ATTENDEE;CN=Betty Test;CUTYPE=INDIVIDUAL;EMAIL=betty@example.com;PARTSTAT=
 NEEDS-ACTION;ROLE=REQ-PARTICIPANT;RSVP=TRUE:urn:uuid:9DC04A71-E6DD-11DF-94
 92-0800200C9A66
ATTENDEE;CN=Amanda Test;CUTYPE=INDIVIDUAL;EMAIL=amanda@example.com;PARTSTA
 T=ACCEPTED:urn:uuid:9DC04A70-E6DD-11DF-9492-0800200C9A66
CREATED:20111101T205355Z
DTSTAMP:20111101T205506Z
ORGANIZER;CN=Amanda Test;EMAIL=amanda@example.com:urn:uuid:9DC04A70-E6DD-1
 1DF-9492-0800200C9A66
SEQUENCE:5
SUMMARY:Repeating
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")


INVITED_TO_MULTIPLE_OCCURRENCES_ICS = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
METHOD:REQUEST
PRODID:-//CALENDARSERVER.ORG//NONSGML Version 1//EN
BEGIN:VTIMEZONE
TZID:America/Los_Angeles
BEGIN:DAYLIGHT
DTSTART:20070311T020000
RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3
TZNAME:PDT
TZOFFSETFROM:-0800
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:20071104T020000
RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11
TZNAME:PST
TZOFFSETFROM:-0700
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:44A391CF-52F5-46B4-B35A-E000E3002084
RECURRENCE-ID;TZID=America/Los_Angeles:20111103T150000
DTSTART;TZID=America/Los_Angeles:20111103T150000
DTEND;TZID=America/Los_Angeles:20111103T170000
ATTENDEE;CN=Betty Test;CUTYPE=INDIVIDUAL;EMAIL=betty@example.com;PARTSTAT=
 NEEDS-ACTION;ROLE=REQ-PARTICIPANT;RSVP=TRUE:urn:uuid:9DC04A71-E6DD-11DF-94
 92-0800200C9A66
ATTENDEE;CN=Amanda Test;CUTYPE=INDIVIDUAL;EMAIL=amanda@example.com;PARTSTA
 T=ACCEPTED:urn:uuid:9DC04A70-E6DD-11DF-9492-0800200C9A66
CREATED:20111101T205355Z
DTSTAMP:20111101T205506Z
ORGANIZER;CN=Amanda Test;EMAIL=amanda@example.com:urn:uuid:9DC04A70-E6DD-1
 1DF-9492-0800200C9A66
SEQUENCE:5
SUMMARY:Repeating
TRANSP:OPAQUE
END:VEVENT
BEGIN:VEVENT
ATTENDEE;CN="Amanda Test";CUTYPE=INDIVIDUAL;PARTSTAT=ACCEPTED:urn:uuid:9
 DC04A70-E6DD-11DF-9492-0800200C9A66
ATTENDEE;CN="Betty Test";CUTYPE=INDIVIDUAL;EMAIL="betty@example.com";PAR
 TSTAT=NEEDS-ACTION;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:betty@example.c
 om
DTEND;TZID=America/Los_Angeles:20111105T170000
TRANSP:OPAQUE
ORGANIZER;CN="Amanda Test":urn:uuid:9DC04A70-E6DD-11DF-9492-0800200C9A66
UID:44A391CF-52F5-46B4-B35A-E000E3002084
DTSTAMP:20111102T162426Z
SEQUENCE:5
RECURRENCE-ID;TZID=America/Los_Angeles:20111105T150000
SUMMARY:Repeating
DTSTART;TZID=America/Los_Angeles:20111105T150000
CREATED:20111101T205355Z
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")


ATTACHMENT_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Apple Inc.//iCal 4.0.1//EN
CALSCALE:GREGORIAN
BEGIN:VTIMEZONE
TZID:US/Pacific
BEGIN:DAYLIGHT
TZOFFSETFROM:-0800
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
DTSTART:20070311T020000
TZNAME:PDT
TZOFFSETTO:-0700
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0700
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
DTSTART:20071104T020000
TZNAME:PST
TZOFFSETTO:-0800
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
CREATED:20100303T195159Z
UID:F2F14D94-B944-43D9-8F6F-97F95B2764CA
DTEND;TZID=US/Pacific:20100304T141500
TRANSP:OPAQUE
SUMMARY:Attachment
DTSTART;TZID=US/Pacific:20100304T120000
DTSTAMP:20100303T195203Z
SEQUENCE:2
X-APPLE-DROPBOX:/calendars/__uids__/6423F94A-6B76-4A3A-815B-D52CFD77935D/dropbox/F2F14D94-B944-43D9-8F6F-97F95B2764CA.dropbox
END:VEVENT
END:VCALENDAR
""".replace("\n", "\r\n")



class PurgePrincipalTests(CommonCommonTests, unittest.TestCase):
    """
    Tests for purging the data belonging to a given principal
    """
    uid = "6423F94A-6B76-4A3A-815B-D52CFD77935D"
    uid2 = "37DB0C90-4DB1-4932-BC69-3DAB66F374F5"

    metadata = {
        "accessMode": "PUBLIC",
        "isScheduleObject": True,
        "scheduleTag": "abc",
        "scheduleEtags": (),
        "hasPrivateComment": False,
    }

    requirements = {
        uid : {
            "calendar1" : {
                "attachment.ics" : (ATTACHMENT_ICS, metadata,),
            }
        },
        uid2 : {
            "calendar2" : {
            }
        },
    }

    @inlineCallbacks
    def setUp(self):
        yield super(PurgePrincipalTests, self).setUp()
        self._sqlCalendarStore = yield buildStore(self, self.notifierFactory)
        yield self.populate()

        self.patch(config.DirectoryService.params, "xmlFile",
            os.path.join(
                os.path.dirname(__file__), "purge", "accounts.xml"
            )
        )
        self.patch(config.ResourceService.params, "xmlFile",
            os.path.join(
                os.path.dirname(__file__), "purge", "resources.xml"
            )
        )
        self.rootResource = getRootResource(config, self._sqlCalendarStore)
        self.directory = self.rootResource.getDirectory()

        txn = self._sqlCalendarStore.newTransaction()

        # Add attachment to attachment.ics
        home = (yield txn.calendarHomeWithUID(self.uid))
        calendar = (yield home.calendarWithName("calendar1"))
        event = (yield calendar.calendarObjectWithName("attachment.ics"))
        attachment = (yield event.createAttachmentWithName("attachment.txt"))
        t = attachment.store(MimeType("text", "x-fixture"))
        t.write("attachment")
        t.write(" text")
        (yield t.loseConnection())

        # Share calendars each way
        home2 = (yield txn.calendarHomeWithUID(self.uid2))
        calendar2 = (yield home2.calendarWithName("calendar2"))
        self.sharedName = (yield calendar2.shareWith(home, _BIND_MODE_WRITE))
        self.sharedName2 = (yield calendar.shareWith(home2, _BIND_MODE_WRITE))

        (yield txn.commit())

        txn = self._sqlCalendarStore.newTransaction()
        home = (yield txn.calendarHomeWithUID(self.uid))
        calendar2 = (yield home.sharedChildWithName(self.sharedName))
        self.assertNotEquals(calendar2, None)
        home2 = (yield txn.calendarHomeWithUID(self.uid2))
        calendar1 = (yield home2.sharedChildWithName(self.sharedName2))
        self.assertNotEquals(calendar1, None)
        (yield txn.commit())


    @inlineCallbacks
    def populate(self):
        yield populateCalendarsFrom(self.requirements, self.storeUnderTest())
        self.notifierFactory.reset()


    def storeUnderTest(self):
        """
        Create and return a L{CalendarStore} for testing.
        """
        return self._sqlCalendarStore


    @inlineCallbacks
    def test_purgeUIDs(self):
        """
        Verify purgeUIDs removes homes, and doesn't provision homes that don't exist
        """

        # Now you see it
        txn = self._sqlCalendarStore.newTransaction()
        home = (yield txn.calendarHomeWithUID(self.uid))
        self.assertNotEquals(home, None)
        (yield txn.commit())

        count, ignored = (yield PurgePrincipalService.purgeUIDs(self.storeUnderTest(), self.directory,
            self.rootResource, (self.uid,), verbose=False, proxies=False, completely=True))
        self.assertEquals(count, 1) # 1 event

        # Now you don't
        txn = self._sqlCalendarStore.newTransaction()
        home = (yield txn.calendarHomeWithUID(self.uid))
        self.assertEquals(home, None)
        # Verify calendar1 was unshared to uid2
        home2 = (yield txn.calendarHomeWithUID(self.uid2))
        self.assertEquals((yield home2.sharedChildWithName(self.sharedName)), None)
        (yield txn.commit())

        count, ignored = (yield PurgePrincipalService.purgeUIDs(self.storeUnderTest(), self.directory,
            self.rootResource, (self.uid,), verbose=False, proxies=False, completely=True))
        self.assertEquals(count, 0)

        # And you still don't (making sure it's not provisioned)
        txn = self._sqlCalendarStore.newTransaction()
        home = (yield txn.calendarHomeWithUID(self.uid))
        self.assertEquals(home, None)
        (yield txn.commit())
