from __future__ import absolute_import
from __future__ import unicode_literals

from itertools import chain
try:
    from urllib.parse import urlencode
except:
    from urllib import urlencode  # noqa

from django import forms
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms.widgets import flatatt
###
from django.forms import widgets
from django.utils.safestring import mark_safe
from django.utils.datastructures import MultiValueDict
###
try:
    from django.utils.encoding import force_text
except:  # pragma: nocover
    from django.utils.encoding import force_unicode as force_text  # noqa
from django.utils.translation import ugettext as _


class LinkWidget(forms.Widget):
    def __init__(self, attrs=None, choices=()):
        super(LinkWidget, self).__init__(attrs)

        self.choices = choices

    def value_from_datadict(self, data, files, name):
        value = super(LinkWidget, self).value_from_datadict(data, files, name)
        self.data = data
        return value

    def render(self, name, value, attrs=None, choices=()):
        if not hasattr(self, 'data'):
            self.data = {}
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs)
        output = ['<ul%s>' % flatatt(final_attrs)]
        options = self.render_options(choices, [value], name)
        if options:
            output.append(options)
        output.append('</ul>')
        return mark_safe('\n'.join(output))

    def render_options(self, choices, selected_choices, name):
        selected_choices = set(force_text(v) for v in selected_choices)
        output = []
        for option_value, option_label in chain(self.choices, choices):
            if isinstance(option_label, (list, tuple)):
                for option in option_label:
                    output.append(
                        self.render_option(name, selected_choices, *option))
            else:
                output.append(
                    self.render_option(name, selected_choices,
                                       option_value, option_label))
        return '\n'.join(output)

    def render_option(self, name, selected_choices,
                      option_value, option_label):
        option_value = force_text(option_value)
        if option_label == BLANK_CHOICE_DASH[0][1]:
            option_label = _("All")
        data = self.data.copy()
        data[name] = option_value
        selected = data == self.data or option_value in selected_choices
        try:
            url = data.urlencode()
        except AttributeError:
            url = urlencode(data)
        return self.option_string() % {
             'attrs': selected and ' class="selected"' or '',
             'query_string': url,
             'label': force_text(option_label)
        }

    def option_string(self):
        return '<li><a%(attrs)s href="?%(query_string)s">%(label)s</a></li>'


class RangeWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = (forms.TextInput(attrs=attrs), forms.TextInput(attrs=attrs))
        super(RangeWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]

    def format_output(self, rendered_widgets):
        return '-'.join(rendered_widgets)


class LookupTypeWidget(forms.MultiWidget):
    def decompress(self, value):
        if value is None:
            return [None, None]
        return value

# Definitions for widget

TPL_OPTION = """<option value="%(value)s" %(selected)s>%(desc)s</option>"""

TPL_SELECT = """
<select class="dropdown_select" %(attrs)s>
%(opts)s
</select>
"""

TPL_SCRIPT = """
<script>
    $('span#%(id)s>select.dropdown_select').change(function(){
        var pattern = 'span#%(id)s>select.dropdown_select';
        var last_item = $(pattern+':last');

        if (last_item.val()) {
            last_item.clone(true).appendTo($('span#%(id)s'));
            $('span#%(id)s').append(' ');
        };

        var values = [];

        for (var i=$(pattern).length-1; i>=0; i--) {
            if (values.indexOf($($(pattern).get(i)).val()) >= 0) {
                $($(pattern).get(i)).remove();
            } else {
                values.push($($(pattern).get(i)).val());
            }
        };
    });
</script>
"""

TPL_FULL = """
<span class="dropdown_multiple" id="%(id)s">
%(values)s
%(script)s
</span>
"""

class DropDownMultiple(widgets.Widget):
    choices = None

    def __init__(self, attrs=None, choices=()):
        self.choices = choices

        super(DropDownMultiple, self).__init__(attrs)

    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = []
        final_attrs = self.build_attrs(attrs, name=name)

        # Pop id
        id = final_attrs['id']
        del final_attrs['id']

        # Insert blank value
        choices = [('','---')] + list(self.choices)

        # Build values
        items = []
        for val in value:
            opts = "\n".join([TPL_OPTION %{'value': k, 'desc': v, 'selected': val == k and 'selected="selected"' or ''} for k, v in choices])

            items.append(TPL_SELECT %{'attrs': flatatt(final_attrs), 'opts': opts})

        # Build blank value
        opts = "\n".join([TPL_OPTION %{'value': k, 'desc': v, 'selected': ''} for k, v in choices])
        items.append(TPL_SELECT %{'attrs': flatatt(final_attrs), 'opts': opts})

        script = TPL_SCRIPT %{'id': id}
        output = TPL_FULL %{'id': id, 'values': '\n'.join(items), 'script': script}

        return mark_safe(output)

    def value_from_datadict(self, data, files, name):
        if isinstance(data, MultiValueDict):
            return [i for i in data.getlist(name) if i]

        return data.get(name, None)
