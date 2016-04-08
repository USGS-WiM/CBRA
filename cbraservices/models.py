from datetime import datetime
from django.core import validators
from django.db import models
from django.contrib.auth.models import User
from django.contrib import admin
from django.conf import settings
from localflavor.us.models import USStateField, USZipCodeField
from simple_history.models import HistoricalRecords
from simple_history.admin import SimpleHistoryAdmin


# Users will be stored in the core User model instead of a custom model.
# Default fields of the core User model: username, first_name, last_name, email, password, groups, user_permissions,
# is_staff, is_active, is_superuser, last_login, date_joined
# For more information, see: https://docs.djangoproject.com/en/1.8/ref/contrib/auth/#user


######
#
#  Abstract Base Classes
#
######


class HistoryModel(models.Model):
    """
    An abstract base class model to track creation, modification, and data change history.
    """

    created_date = models.DateField(default=datetime.now, null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, db_index=True,
                                   related_name='%(class)s_creator')
    modified_date = models.DateField(auto_now=True, null=True, blank=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, db_index=True,
                                    related_name='%(class)s_modifier')
    history = HistoricalRecords()

    class Meta:
        abstract = True
        default_permissions = ('add', 'change', 'delete', 'view')


class AddressModel(HistoryModel):
    """
    An abstract base class model for common address fields.
    """

    street = models.CharField(max_length=255, blank=True)
    unit = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    state = USStateField(null=True, blank=True)
    zipcode = USZipCodeField(null=True, blank=True)

    class Meta:
        abstract = True


######
#
#  Determinations
#
######


class Case(HistoryModel):
    """
    An official case to document the CBRA determination for a property on behalf of a requester.
    The analyst, QC reviewer, and FWS reviewer must always be three different persons.
    """

    def _get_id(self):
        """Returns the id of the record"""
        return '%s' % self.id

    def _get_status(self):
        """Returns the status of the record"""
        if self.close_date and not self.final_letter_date:
            return 'Closed with no Final Letter'
        elif self.close_date:
            return 'Final'
        elif self.fws_reviewer_signoff_date:
            return 'Awaiting Final Letter'
        elif self.qc_reviewer_signoff_date:
            return 'Awaiting FWS Review'
        elif self.analyst_signoff_date:
            return 'Awaiting QC'
        else:
            return 'Received'

    # for new records, there is a custom signal receiver in the receivers.py file listening for
    # the post_save event signal, and when the post_save's 'created' boolean is true,
    # this custom receiver will create the case hash (public ID) and send a confirmation email

    case_number = property(_get_id)
    case_hash = models.CharField(max_length=255, blank=True)
    status = property(_get_status)
    request_date = models.DateField(default=datetime.now().date())
    requester = models.ForeignKey('Requester', related_name='cases')
    property = models.ForeignKey('Property', related_name='cases')
    cbrs_unit = models.ForeignKey('SystemUnit', null=True, blank=True)
    map_number = models.ForeignKey('SystemMap', null=True, blank=True)
    cbrs_map_date = models.DateField(null=True, blank=True)
    determination = models.ForeignKey('Determination', null=True, blank=True)
    prohibition_date = models.DateField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)
    fws_fo_received_date = models.DateField(null=True, blank=True)
    fws_hq_received_date = models.DateField(null=True, blank=True)
    final_letter_date = models.DateField(null=True, blank=True)
    close_date = models.DateField(null=True, blank=True)
    final_letter_recipient = models.CharField(max_length=255, blank=True)
    analyst = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='analyst', null=True, blank=True)
    analyst_signoff_date = models.DateField(null=True, blank=True)
    qc_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='qc_reviewer', null=True, blank=True)
    qc_reviewer_signoff_date = models.DateField(null=True, blank=True)
    fws_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='fws_reviewer', null=True, blank=True)
    fws_reviewer_signoff_date = models.DateField(null=True, blank=True)
    priority = models.BooleanField(default=False)
    tags = models.ManyToManyField('Tag', through='CaseTag', related_name='cases')

    def __str__(self):
        return self.case_number

    class Meta:
        db_table = "cbra_case"


class CaseFile(HistoryModel):
    """
    File "attached" to a case to assist with determination, which can be uploaded by either
    the requester or by CBRA staff. Can be a map, picture, letter, or any number of things.
    For easier management, file sizes will be limited to ~2MB, and file types will be limited to the following:
    txt, pdf, doc, jpeg, png, gif, tif, bmp, shp, zip, (others?).
    """

    def _get_filename(self):
        """Returns the name of the file"""
        return '%s' % str(self.file).split('/')[-1]

    def casefile_location(instance, filename):
        """Returns a custom location for the case file, in a folder named for its case"""
        #print(instance.uploader_id)
        if not instance.uploader_id:
            return 'casefiles/{0}/requester/{1}'.format(instance.case, filename)
        else:
            return 'casefiles/{0}/{1}'.format(instance.case, filename)

    name = property(_get_filename)
    file = models.FileField(upload_to=casefile_location)
    case = models.ForeignKey('Case', related_name='case_files')
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="case_files")
    uploaded_date = models.DateField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = "cbra_casefile"
        unique_together = ("file", "case")


# class CaseFile(HistoryModel):
#     """
#     File "attached" to a case to assist with determination, which can be uploaded by either
#     the requester or by CBRA staff. Can be a map, picture, letter, or any number of things.
#     For easier management, file sizes will be limited to ~2MB, and file types will be limited to the following:
#     txt, pdf, doc, jpeg, png, gif, tif, bmp, shp, zip, (others?).
#     """
#
#     def _get_filename(self):
#         """Returns the name of the file"""
#         return '%s' % str(self.file).split('/')[-1]
#
#     @staticmethod
#     def get_upload_to():
#         """Returns the upload_to location with the proper operating system path separator"""
#         # if platform.system() == 'Windows':
#         #     return 'cbraservices.DatabaseFile\\bytes\\filename\\mimetype'
#         # else:
#         #     return 'cbraservices.DatabaseFile/bytes/filename/mimetype'
#         print(os.path.sep)
#         up = 'cbraservices.DatabaseFile' + os.path.sep + 'bytes' + os.path.sep + 'filename' + os.path.sep + 'mimetype'
#         print(up)
#         return '%s' % up
#
#     name = property(_get_filename)
#     file = models.FileField(upload_to='cbraservices.DatabaseFile/bytes/filename/mimetype') #, blank=True, null=True)
#     case = models.ForeignKey('Case', related_name='case_files')
#     uploaded_date = models.DateField(auto_now_add=True, null=True, blank=True)
#
#     def __str__(self):
#         return str(self.name)
#
#     class Meta:
#         db_table = "cbra_casefile"
#         unique_together = ("file", "case")
#
#
# class DatabaseFile(models.Model):
#     """
#     Table to store files in the database, rather than in the server file system.
#     """
#
#     bytes = models.TextField()
#     filename = models.CharField(max_length=255)
#     mimetype = models.CharField(max_length=255)
#
#     def __str__(self):
#         return str(self.filename)
#
#     class Meta:
#         db_table = "cbra_databasefile"


class Property(AddressModel):
    """
    A real estate property for which a CBRA determination has been requested.
    """

    # other fields for lot number, legal descriptions, lat/lon, etc, need to be discussed
    subdivision = models.CharField(max_length=255, blank=True)
    policy_number = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.street + ", " + self.city + ", " + self.state + ", " + self.zipcode

    class Meta:
        db_table = "cbra_property"
        unique_together = ("street", "unit", "city", "state", "zipcode")
        verbose_name_plural = "properties"


class Requester(AddressModel):
    """
    Name and contact information of the person making the request for a determination.
    """

    salutation = models.CharField(max_length=16, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=255, blank=True, validators=[validators.EmailValidator])

    def __str__(self):
        return self.first_name + " " + self.last_name

    class Meta:
        db_table = "cbra_requester"
        unique_together = ("salutation", "first_name", "last_name", "organization", "email",
                           "street", "unit", "city", "state", "zipcode")


######
#
#  Tags
#
######


class CaseTag(HistoryModel):
    """
    Table to allow many-to-many relationship between Cases and Tags.
    """

    case = models.ForeignKey('Case')
    tag = models.ForeignKey('Tag')
    history = HistoricalRecords()

    def __str__(self):
        return str(self.case) + " - " + str(self.tag)

    class Meta:
        db_table = "cbra_casetag"
        unique_together = ("case", "tag")


class Tag(HistoryModel):
    """
    Terms or keywords used to describe, categorize, or group similar Cases for easier searching and reporting.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cbra_tag"


######
#
#  Comments
#
######


class Comment(HistoryModel):
    """
    Comments by CBRA staff about cases. Can be used for conversations between CBRA staff about cases.
    Possibly replace this model with the Django excontrib Comments module?
    http://django-contrib-comments.readthedocs.org/en/latest/index.html
    """

    comment = models.TextField()
    case = models.ForeignKey('Case', related_name='comments')

    def __str__(self):
        return self.comment

    class Meta:
        db_table = "cbra_comment"
        unique_together = ("comment", "case")


######
#
#  Lookup Tables
#
######


class Determination(HistoryModel):
    """
    Lookup table for official determination values, which are as follows:
    "In", "Out", "Partially In; Structure In", "Partially In; Structure Out", "Partially In/No Structure".
    Property is always mentioned first, then the structure if necessary.
    """

    determination = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.determination

    class Meta:
        db_table = "cbra_determination"


class SystemUnit(HistoryModel):
    """
    Lookup table for CBRS System Units.
    """

    system_unit_number = models.CharField(max_length=16, unique=True)
    system_unit_name = models.CharField(max_length=255, blank=True)
    field_office = models.ForeignKey('FieldOffice', related_name='system_units', null=True, blank=True)
    system_maps = models.ManyToManyField('SystemMap', through='SystemUnitMap', related_name='system_units')

    def __str__(self):
        return self.system_unit_number

    class Meta:
        db_table = "cbra_systemunit"


class SystemUnitProhibitionDate(HistoryModel):
    """
    Lookup table for Prohibition Dates for System Units.
    """

    prohibition_date = models.DateField()
    system_unit = models.ForeignKey('SystemUnit', related_name='prohibition_dates')

    def __str__(self):
        return self.prohibition_date

    class Meta:
        db_table = "cbra_systemunitprohibitiondate"
        ordering = ['-prohibition_date']
        unique_together = ("prohibition_date", "system_unit")


class SystemUnitMap(HistoryModel):
    """
    Table to allow many-to-many relationship between System Units and Maps.
    """

    system_unit = models.ForeignKey('SystemUnit')
    system_map = models.ForeignKey('SystemMap')
    history = HistoricalRecords()

    def __str__(self):
        return str(self.system_unit) + " - " + str(self.system_map)

    class Meta:
        db_table = "cbra_systemunitmap"
        unique_together = ("system_unit", "system_map")


class SystemMap(HistoryModel):
    """
    Lookup table for Maps for System Units.
    """

    map_number = models.CharField(max_length=16)
    map_title = models.CharField(max_length=255, blank=True)
    map_date = models.DateField()

    def __str__(self):
        return self.map_number

    class Meta:
        db_table = "cbra_systemmap"
        unique_together = ("map_number", "map_date")


class FieldOffice(HistoryModel):
    """
    Lookup table for Field Offices for System Units.
    """

    field_office_number = models.CharField(max_length=16, unique=True)
    field_office_name = models.CharField(max_length=255, blank=True)
    field_agent_name = models.CharField(max_length=255, blank=True)
    field_agent_email = models.CharField(max_length=255, blank=True, validators=[validators.EmailValidator])
    city = models.CharField(max_length=255, blank=True)
    state = USStateField(null=True, blank=True)

    def __str__(self):
        return self.city + ", " + self.state

    class Meta:
        db_table = "cbra_fieldoffice"