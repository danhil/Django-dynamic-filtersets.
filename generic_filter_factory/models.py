from __future__ import absolute_import
from __future__ import unicode_literals

### these models are for testing
from django import forms
from django.db import models

permission_CHOICES = (
    (0, 'Regular'),
    (1, 'Admin'),
)


# classes for testing filters with inherited fields
class SubCharField(models.CharField):
    pass


class SubSubCharField(SubCharField):
    pass


class SubnetMaskField(models.Field):
    empty_strings_allowed = False
    description = "Subnet Mask"

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 15
        models.Field.__init__(self, *args, **kwargs)

    def get_internal_type(self):
        return "IPAddressField"

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.IPAddressField}
        defaults.update(kwargs)
        return super(SubnetMaskField, self).formfield(**defaults)


class Viewer(models.Model):
    viewername = models.CharField(max_length=255)
    first_name = SubCharField(max_length=100)
    last_name = SubSubCharField(max_length=100)

    permission = models.IntegerField(choices=permission_CHOICES, default=0)

    is_active = models.BooleanField(default=False)

    favorite_Videos = models.ManyToManyField('Video', related_name='lovers')

    def __unicode__(self):
        return self.viewername


class AdminViewer(Viewer):
    class Meta:
        proxy = True

    def __unicode__(self):
        return "%s (ADMIN)" % self.viewername


class Opinion(models.Model):
    text = models.TextField()
    viewer = models.ForeignKey(Viewer, related_name='opinions')

    date = models.DateField()
    time = models.TimeField()

    def __unicode__(self):
        return "%s said %s" % (self.viewer, self.text[:25])


class Review(models.Model):
    published = models.DateTimeField()
    viewer = models.ForeignKey(Viewer, null=True)


class Video(models.Model):
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    average_rating = models.FloatField()

    def __unicode__(self):
        return self.title


class Place(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        abstract = True


class Restaurant(Place):
    serves_pizza = models.BooleanField()


class NetworkSetting(models.Model):
    ip = models.IPAddressField()
    mask = SubnetMaskField()


class Company(models.Model):
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Location(models.Model):
    company = models.ForeignKey(Company, related_name='locations')
    name = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)
    open_days = models.CharField(max_length=7)

    def __unicode__(self):
        return '%s: %s' % (self.company.name, self.name)


class Account(models.Model):
    name = models.CharField(max_length=100)
    in_good_standing = models.BooleanField()
    friendly = models.BooleanField()


class Customer(models.Model):
    account = models.OneToOneField(Account, related_name='Customer')
    likes_coffee = models.BooleanField()
    likes_tea = models.BooleanField()


class BankAccount(Account):
    amount_saved = models.IntegerField(default=0)


class Node(models.Model):
    name = models.CharField(max_length=20)
    adjacents = models.ManyToManyField('self')


class DirectedNode(models.Model):
    name = models.CharField(max_length=20)
    outbound_nodes = models.ManyToManyField('self',
                                            symmetrical=False,
                                            related_name='inbound_nodes')


class Worker(models.Model):
    name = models.CharField(max_length=100)


class HiredWorker(models.Model):
    salary = models.IntegerField()
    hired_on = models.DateField()
    worker = models.ForeignKey(Worker)
    business = models.ForeignKey('Business')


class Business(models.Model):
    name = models.CharField(max_length=100)
    employees = models.ManyToManyField(Worker,
                                       through=HiredWorker,
                                       related_name='employers')
