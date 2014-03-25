from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import timedelta

from django import forms
from django.db.models import Q
from django.db.models.related import RelatedObject
from django.db.models.sql.constants import QUERY_TERMS
from django.db.models.constants import LOOKUP_SEP
from django.utils import six
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from .fields import RangeField, LookupTypeField
from django.db.models import ForeignKey, ManyToManyField
from django.db.models.fields import FieldDoesNotExist

RELATED_FIELD_TYPES = (ForeignKey, ManyToManyField)


__all__ = [
    'Filter', 'CharFilter', 'BooleanFilter', 'ChoiceFilter',
    'MultipleChoiceFilter', 'DateFilter', 'DateTimeFilter', 'TimeFilter',
    'ModelChoiceFilter', 'ModelMultipleChoiceFilter', 'NumberFilter',
    'RangeFilter', 'DateRangeFilter', 'AllValuesFilter', 'UpdatingValuesFilter',
    'UpdatingValuesMultipleSelectFilter', 'UpdatingKeyFilter',
]


LOOKUP_TYPES = sorted(QUERY_TERMS)
DEFAULT_FILTER_EMPTY_FIELD = "empty"
DEFAULT_FILTER_EMPTY_LABEL = "Select"
NOT_WANTED_IN_FORM_FIELD = set(['', ])

'''
Metaclass for all of the filters. Contains the filtering functionality and form field creation
'''


class Filter(object):
    creation_counter = 0
    field_class = forms.Field

    def __init__(self, name=None, label=None, widget=None, action=None,
                 lookup_type='exact', required=False, distinct=False, **kwargs):
        self.name = name
        self.label = label
        if action:
            self.filter = action
        self.lookup_type = lookup_type
        self.widget = widget
        self.required = required
        self.extra = kwargs
        self.distinct = distinct
        self.attributequeryset = None

        self.creation_counter = Filter.creation_counter
        Filter.creation_counter += 1

    def filter(self, qs, value):
        # If there is no value to filter on or the value is the specified "default" value, no filtering
        # is to be done and the queryset is returned.
        if not value or value == DEFAULT_FILTER_EMPTY_FIELD:
            return qs
        # We have specified a lookup type...
        #if isinstance(value, (list, tuple)):
            #try:
                #lookup = six.text_type(value[1])
            #except:
                #lookup = None
            #if not lookup:
                #lookup = 'exact'  # fallback to exact if lookup is not provided
            #value = value[0]
        #else:
        lookup = self.lookup_type

        if value:
            # A value is present to filter on, send it in a a kwarg as python does not allow
            # expressions in the filter field.
            if isinstance(value, list):
                finalqs = qs.filter(**{'%s__%s' % (self.name, lookup): value[0]})
                for val in value[1:]:
                    finalqs | qs.filter(**{'%s__%s' % (self.name, lookup): val})
                qs = finalqs
            else:
                qs = qs.filter(**{'%s__%s' % (self.name, lookup): value})
        if self.distinct:
            qs = qs.distinct()
        return qs

 # Determines the type of form field to be used in the form.
    def setField(self, qs=None):
        if not hasattr(self, '_field'):
            if (self.lookup_type is None or
                    isinstance(self.lookup_type, (list, tuple))):

                if self.lookup_type is None:
                    lookup = [(x, x) for x in LOOKUP_TYPES]
                else:
                    lookup = [
                        (x, x) for x in LOOKUP_TYPES if x in self.lookup_type]
                self._field = LookupTypeField(self.field_class(
                    required=self.required, widget=self.widget, **self.extra),
                    lookup, required=self.required, label=self.label)

            else:
                self._field = self.field_class(required=self.required,
                                               label=self.label, widget=self.widget, **self.extra)

        return self._field


''' Different types of filters and their related field class.
'''


class CharFilter(Filter):
    field_class = forms.CharField


class BooleanFilter(Filter):
    field_class = forms.NullBooleanField

    def filter(self, qs, value):
        if value is not None:
            qs = qs.filter(**{self.name: value})
        return qs


class ChoiceFilter(Filter):
    field_class = forms.ChoiceField


class MultipleChoiceFilter(Filter):
    """
    This filter preforms an OR query on the selected options.
    """
    field_class = forms.MultipleChoiceField

    def filter(self, qs, value=None):
        value = value or ()
        if len(value) == len(self.setField().choices):
            return qs
        q = Q()
        for v in value:
            q |= Q(**{self.name: v})
        qs = qs.filter(q).distinct()
        Filter.attributequeryset = qs
        return qs


class DateFilter(Filter):
    field_class = forms.DateField


class DateTimeFilter(Filter):
    field_class = forms.DateTimeField


class TimeFilter(Filter):
    field_class = forms.TimeField


class ModelChoiceFilter(Filter):
    field_class = forms.ModelChoiceField


class ModelMultipleChoiceFilter(MultipleChoiceFilter):
    field_class = forms.ModelMultipleChoiceField


class NumberFilter(Filter):
    field_class = forms.DecimalField


class RangeFilter(Filter):
    field_class = RangeField

    def filter(self, qs, value=None):
        if value:
            lookup = '%s__range' % self.name
            return qs.filter(**{lookup: (value.start, value.stop)})
        return qs


_truncate = lambda dt: dt.replace(hour=0, minute=0, second=0)


class DateRangeFilter(ChoiceFilter):
    options = {
        '': (_('Any date'), lambda qs, name: qs.all()),
        1: (_('Today'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month,
            '%s__day' % name: now().day
        })),
        2: (_('Past 7 days'), lambda qs, name: qs.filter(**{
            '%s__gte' % name: _truncate(now() - timedelta(days=7)),
            '%s__lt' % name: _truncate(now() + timedelta(days=1)),
        })),
        3: (_('This month'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
            '%s__month' % name: now().month
        })),
        4: (_('This year'), lambda qs, name: qs.filter(**{
            '%s__year' % name: now().year,
        })),
    }

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = [
            (key, value[0]) for key, value in six.iteritems(self.options)]
        super(DateRangeFilter, self).__init__(*args, **kwargs)

    def filter(self, qs, value=None):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = ''
        return self.options[value][1](qs, self.name)


class AllValuesFilter(ChoiceFilter):
    def setField(self, qs=None):
        qs = self.model._default_manager.distinct()
        qs = qs.order_by(self.name).values_list(self.name, flat=True)
        self.extra['choices'] = [(o, o) for o in qs]
        return super(AllValuesFilter, self).setField()


'''
These are filters for dynamic updating of the alternatives on form submission
'''


class UpdatingValuesFilter(ChoiceFilter):
    def setField(self, qs=None):
        if qs is None:
            qs = self.model.objects.all()
        #else:
            #qs = self.attributequeryset

        # Need to index large fields if the ordering attribute is to be used...
        # qs = qs.order_by(self.name).values_list(self.name, flat=True)
        qs = qs.values_list(self.name, flat=True)

        #Populate the choices dict, this is uesd to display the available choices in the form.
        self.extra['choices'] = [(DEFAULT_FILTER_EMPTY_FIELD, DEFAULT_FILTER_EMPTY_LABEL)]

        for o in qs:
            #If it is a string we do not want to include some chars in the fileds(like blank and -)
            if isinstance(o, basestring):
                # If the attribute o is the same in multiple objects, only display one alternative.
                if o.strip() not in NOT_WANTED_IN_FORM_FIELD and (o, o) not in self.extra['choices']:
                    self.extra['choices'] += [(o, o)]
            else:
                    if (o, o) not in self.extra['choices']:
                        self.extra['choices'] += [(o, o)]

        return super(UpdatingValuesFilter, self).setField()


# Multipleselect that filters on the selected values, widgets for the selectbox can be specified
# in the API filtertype declaration.
class UpdatingValuesMultipleSelectFilter(MultipleChoiceFilter):
    def setField(self, qs=None):
        if qs is None:
            qs = self.model.objects.all()
        #else:
            #qs = self.attributequeryset
        # qs = qs.order_by(self.name).values_list(self.name, flat=True)
        qs = qs.values_list(self.name, flat=True)

         #Populate the choices dict, this is uesd to display the available choices in the form.
        self.extra['choices'] = [(DEFAULT_FILTER_EMPTY_FIELD, DEFAULT_FILTER_EMPTY_LABEL)]

        for o in qs:
            #If it is a string we do not want to include some chars in the fileds(like blank and -)
            if isinstance(o, basestring):
                # If the attribute o is the same in multiple objects, only display one alternative.
                if o.strip() not in NOT_WANTED_IN_FORM_FIELD and (o, o) not in self.extra['choices']:
                    self.extra['choices'] += [(o, o)]
            else:
                    if (o, o) not in self.extra['choices']:
                        self.extra['choices'] += [(o, o)]
        return super(UpdatingValuesMultipleSelectFilter, self).setField()


'''
Filter that maps between foreign and manytomany relationships
and updates the filter dropdowns dynamically.
'''


def get_model_objects(model, f, qs):
    # returns the models field type.
    parts = f.split(LOOKUP_SEP)
    opts = model._meta
    for name in parts[:-1]:
        try:
            rel = opts.get_field_by_name(name)[0]
        except FieldDoesNotExist:
            return None
        if isinstance(rel, RelatedObject):
            model = rel.model
            opts = rel.opts
        else:
            model = rel.rel.to
            opts = model._meta
    try:
        opts, model, direct, m2m = opts.get_field_by_name(parts[-1])  # rel, model, direct, m2m = opts.get_field_by_name(parts[-1])
        if isinstance(opts, RELATED_FIELD_TYPES):
            return opts.rel.to.objects.filter(pk__in=qs)
    except FieldDoesNotExist:
        return None
    return opts


class UpdatingKeyFilter(ModelChoiceFilter):
    def setField(self, qs=None):
                if qs is None:
                    qs = self.model.objects.values_list(self.name).distinct()
                else:
                    qs = qs.select_related(self.name).distinct().values_list(self.name)
                    #self.attributequeryset = self.attributequeryset.select_related(self.name).distinct()
                    #qs = self.attributequeryset.values_list(self.name).distinct()
                # Need to "make" our own queryset in order too feed it to the ModelChoicefields extra args.
                # Produce a "real" queryset, there is no better way at the moment (Django 1.5.1).
                # We get all of the objects that are related to our models and that should be displayed.
                #qs = self.model._meta.get_field(self.name).rel.to.objects.filter(pk__in=qs)
                qs = get_model_objects(self.model, self.name, qs)
                #qs = model.objects.filter(pk__in=qs)
                self.extra['queryset'] = qs
                return super(UpdatingKeyFilter, self).setField()
