from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.db.models.related import RelatedObject
from django.db.models import ForeignKey, ManyToManyField
from django.db.models.constants import LOOKUP_SEP
from django.forms import Select
from django.utils import six
from django.utils.datastructures import SortedDict
from django.utils.text import capfirst
from copy import deepcopy
from .filters import (Filter, CharFilter, BooleanFilter,
    ChoiceFilter, DateFilter, DateTimeFilter, TimeFilter, ModelChoiceFilter,
    ModelMultipleChoiceFilter, NumberFilter,UpdatingValuesFilter,UpdatingKeyFilter,
  )


# Could be 'o'
ORDER_BY_FIELD = 'o'
RELATED_FIELD_TYPES = (ForeignKey, ManyToManyField)


def getFilters(bases, attrs, with_base_filters=True):
    filters = []
    for filter_name, obj in list(attrs.items()):
        if isinstance(obj, Filter):
            obj = attrs.pop(filter_name)
            if getattr(obj, 'name', None) is None:
                obj.name = filter_name
            filters.append((filter_name, obj))
    filters.sort(key=lambda x: x[1].creation_counter)

    if with_base_filters:
        for base in bases[::-1]:
            if hasattr(base, 'base_filters'):
                filters = list(base.base_filters.items()) + filters
    else:
        for base in bases[::-1]:
            if hasattr(base, 'declared_filters'):
                filters = list(base.declared_filters.items()) + filters

    return SortedDict(filters)


def getModelMetaField(model, f):
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
        rel, model, direct, m2m = opts.get_field_by_name(parts[-1])
    except FieldDoesNotExist:
        return None
    return rel

# Here we look at the defined filer models, and populate them with the right filters.
def filters_for_model(model, fields=None, exclude=None,):
    field_dict = SortedDict()
    opts = model._meta
    if fields is None:
        #Populate the different fields in the declared filterset, eg one per declared filter.
        fields = [f.name for f in sorted(opts.fields + opts.many_to_many)
            if not isinstance(f, models.AutoField)]

    for f in fields:
        #We define the filters used here and populate them.
        if exclude is not None and f in exclude:
            continue
        field = getModelMetaField(model, f)
        if field is None:
            field_dict[f] = None
            continue
        if isinstance(field, RelatedObject):
            rel = field.field.rel
            queryset = field.model._default_manager.all()
            default = {
                'name': f,
                'label': capfirst(rel.related_name),
                'queryset': queryset,
            }
            filter_ = UpdatingKeyFilter(**default)
        else:
            filter_for_field = dict(DEFAULT_FILTER_FOR_DATABASEFIELD)
            default = {
                'name': f,
                'label': capfirst(field.verbose_name)
            }

            if field.choices:
                default['choices'] = field.choices
                filter_ = ChoiceFilter(**default)
            else:
                data = filter_for_field.get(field.__class__)
                if data is None:
                    # could be a derived field, inspect parents
                    for class_ in field.__class__.mro():
                        # skip if class_ is models.Field or object
                        # 1st item in mro() is original class
                        if class_ in (field.__class__, models.Field, object):
                            continue
                        data = filter_for_field.get(class_)
                        if data:
                            break

                if data is not None:
                    filter_class = data.get('filter_class')
                    default.update(data.get('extra', lambda f: {})(field))

                    if filter_class is not None:
                        filter_ = filter_class(**default)

        if filter_:
            # Here we build a dictionary with the filters defined in each main filter.
            field_dict[f] = filter_
    return field_dict


# Run to initialize the filterset run ONCE
class FilterSetOptions(object):
    def __init__(self, options=None):
        self.model = getattr(options, 'model', None)
        self.form = getattr(options, 'form', forms.Form)
        self.fields = getattr(options, 'fields', None)
        self.labels = getattr(options, 'labels', None)
        self.form_labels = None
        self.form_fields = None
        self.exclude = getattr(options, 'exclude', None)
        self.order_by = getattr(options, 'order_by', False)


# Run to initialize the filterset, run ONCE
class FilterSetMetaclass(type):
    def __new__(cls, name, bases, attrs):
        try:
            parents = [b for b in bases if issubclass(b, FilterSet)]
        except NameError:
            # We are defining FilterSet itself here
            parents = None
        declared_filters = getFilters(bases, attrs, False)
        new_class = super(
            FilterSetMetaclass, cls).__new__(cls, name, bases, attrs)

        if not parents:
            return new_class

        opts = new_class._meta = FilterSetOptions(
            getattr(new_class, 'Meta', None))
        if opts.model:
            filters = filters_for_model(opts.model, opts.fields, opts.exclude,)
            filters.update(declared_filters)
        else:
            filters = declared_filters

        if None in filters.values():
            raise TypeError("Meta.fields contains a field that isn't defined "
                            "on this FilterSet")

        new_class.declared_filters = declared_filters
        new_class.base_filters = filters
        # Here the filter "label" attribute is read and set in meta class form_label attribute
        labels = []
        for filter in new_class.base_filters.values():
            if filter.label is None:
                labels.append(filter.name)
            else:
                labels.append(filter.label)
        new_class._meta.form_labels = labels
        new_class._meta.form_fields = new_class.base_filters.keys()
        return new_class

#Filter defaults for the filtersets.
DEFAULT_FILTER_FOR_DATABASEFIELD = {
    models.AutoField: {
        'filter_class': NumberFilter
    },
    models.CharField: {
        'filter_class': UpdatingValuesFilter
    },
    models.TextField: {
        'filter_class': CharFilter
    },
    models.BooleanField: {
        'filter_class': BooleanFilter
    },
    models.DateField: {
        'filter_class': DateFilter
    },
    models.DateTimeField: {
        'filter_class': DateTimeFilter
    },
    models.TimeField: {
        'filter_class': TimeFilter
    },
    models.OneToOneField: {
        'filter_class': ModelChoiceFilter,
        'extra': lambda f: {
            'queryset': f.rel.to._default_manager.complex_filter(
                f.rel.limit_choices_to),
            'to_field_name': f.rel.field_name,
            'widget': Select(attrs={"onChange": 'this.form.submit()'}),
        }
    },
    models.ForeignKey: {
        'filter_class': UpdatingKeyFilter,
        'extra': lambda f: {
            'queryset': f.rel.to._default_manager.complex_filter(
                f.rel.limit_choices_to),
            'to_field_name': f.rel.field_name,

        }
    },
    models.ManyToManyField: {
        'filter_class': UpdatingKeyFilter,
        'extra': lambda f: {
            'queryset': f.rel.to._default_manager.complex_filter(
                f.rel.limit_choices_to),
        }
    },
    models.DecimalField: {
        'filter_class': NumberFilter,
    },
    models.SmallIntegerField: {
        'filter_class': NumberFilter,
    },
    models.IntegerField: {
        'filter_class': NumberFilter,
    },
    models.PositiveIntegerField: {
        'filter_class': NumberFilter,
    },
    models.PositiveSmallIntegerField: {
        'filter_class': NumberFilter,
    },
    models.FloatField: {
        'filter_class': NumberFilter,
    },
    models.NullBooleanField: {
        'filter_class': BooleanFilter,
    },
    models.SlugField: {
        'filter_class': CharFilter,
    },
    models.EmailField: {
        'filter_class': CharFilter,
    },
    models.FilePathField: {
        'filter_class': CharFilter,
    },
    models.URLField: {
        'filter_class': CharFilter,
    },
    models.IPAddressField: {
        'filter_class': CharFilter,
    },
    models.CommaSeparatedIntegerField: {
        'filter_class': CharFilter,
    },
}


class BaseFilterSet(object):
    filter_overrides = {}
    order_by_field = ORDER_BY_FIELD
    # The attributequeryset is to update the fields in the autogenerated form.
    # i one changes the first query the filterqueryset must still be all of the objects.

    def __init__(self, data=None, queryset=None, prefix=None):
        self.is_bound = data is not None
        self.data = data or {}
        if queryset is None:
            queryset = self._meta.model.objects.all()
        self.queryset = queryset
        self.form_prefix = prefix
        self.filters = deepcopy(self.base_filters)
        # propagate the model being used through the filters
        for filter_ in self.filters.values():
            filter_.model = self._meta.model

    def __iter__(self):
        for obj in self.qs:
            yield obj

    def __len__(self):
        return len(self.qs)

    def __getitem__(self, key):
        return self.qs[key]

    @property
    def form(self):
        if not hasattr(self, '_form'):
            # If the filter is a updatingValuesFilter we want the filter attributes to be updated.
            #Check the filters.py  basefilter.filter to see how this is done.
            # A dictionary that keeps its keys in the order in which they're inserted.
            fields = SortedDict([
                (name, filter_.setField(self._qs))
                for name, filter_ in six.iteritems(self.filters)])

            fields[self.order_by_field] = self.ordering_field

            Form = type(str('%sForm' % self.__class__.__name__),
                        (self._meta.form,), fields,)

            if self.is_bound:
                self._form = Form(self.data,  prefix=self.form_prefix)
            else:
                self._form = Form(prefix=self.form_prefix)

        return self._form

    def get_ordering_field(self):
        if self._meta.order_by:
            if isinstance(self._meta.order_by, (list, tuple)):
                if isinstance(self._meta.order_by[0], (list, tuple)):
                    # e.g. (('field', 'Display name'), ...)
                    choices = [(f[0], f[1]) for f in self._meta.order_by]
                else:
                    choices = [(f, capfirst(f)) for f in self._meta.order_by]
            else:
                # use the filter's label if provided
                choices = [(fltr.name or f, fltr.label or capfirst(f))
                           for f, fltr in self.filters.items()]
            return forms.ChoiceField(label="Ordering", required=False,
                                     choices=choices)

    @property
    def ordering_field(self):
        if not hasattr(self, '_ordering_field'):
            self._ordering_field = self.get_ordering_field()
        return self._ordering_field

    @property
    def qs(self):
        if not hasattr(self, '_qs'):
            qs = self.queryset
            #Iterate through the filters and filter.
            for name, filter_ in six.iteritems(self.filters):
                # We have submitted data to filter on, otherwise just render form.
                if self.data:
                    val = self.data.get(name)
                    qs = filter_.filter(qs, val)
                # For performance gains over all of the filters the prefetch related is used, due to
                # the usage of the querys in updating the dropdowns one can be sure that the query is evalu
                # ated..
                if isinstance(getModelMetaField(filter_.model, name), RELATED_FIELD_TYPES):
                    qs = qs.prefetch_related(name)
            #qs = qs.select_related()
            #The final queryset is distrubuted to the filters, as when their fields are populated
            #the queryset must be right.
            #for name, filter_ in six.iteritems(self.filters):
                # The attribute queryset is the queryset to be used when defining the filter attributes.
                #filter_.attributequeryset = qs

            self._qs = qs
            # create the form
            self.form

            if self._meta.order_by:
                try:
                    order_field = self.form.fields[self.order_by_field]
                    data = self.form[self.order_by_field].data
                    value = order_field.clean(data)
                    if value:
                        qs = qs.order_by(value)
                        self._qs = qs
                except forms.ValidationError:
                    pass

        return self._qs

    def count(self):
        return self.qs.count()


# create a new class with base class BaseFilterSet and metaclass FilterSetMetaclass
class FilterSet(six.with_metaclass(FilterSetMetaclass, BaseFilterSet)):
    pass


def filterset_factory(model):
    meta = type(str('Meta'), (object,), {'model': model})
    filterset = type(str('%sFilterSet' % model._meta.object_name),
                     (FilterSet,), {'Meta': meta})
    return filterset
