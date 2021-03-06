"""
Custom generic managers
"""
from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import get_language
from django.utils import six
from parler import appsettings
from parler.utils import get_active_language_choices


class TranslatableQuerySet(QuerySet):
    """
    An enhancement of the QuerySet which sets the objects language before they are returned.

    When using this method with *django-polymorphic*, make sure this
    class is first in the chain of inherited classes.
    """

    def __init__(self, *args, **kwargs):
        super(TranslatableQuerySet, self).__init__(*args, **kwargs)
        self._language = []


    def _clone(self, klass=None, setup=False, **kw):
        c = super(TranslatableQuerySet, self)._clone(klass, setup, **kw)
        c._language = self._language
        return c


    def language(self, language_code=None):
        """
        Set the language code to assign to objects retrieved using this QuerySet.
        """
        if language_code is None:
            language_code = appsettings.PARLER_LANGUAGES.get_default_language()

        self._language = language_code
        return self


    def translated(self, *language_codes, **translated_fields):
        """
        Only return translated objects which of the given languages.

        When no language codes are given, only the currently active language is returned.

        NOTE: due to Django `ORM limitations <https://docs.djangoproject.com/en/dev/topics/db/queries/#spanning-multi-valued-relationships>`_,
        this method can't be combined with other filters that access the translated fields. As such, query the fields in one filter:

        .. code-block:: python

            qs.translated('en', name="Cheese Omelette")

        This will query the translated model for the ``name`` field.
        """
        relname = self.model._translations_field

        if not language_codes:
            language_codes = (get_language(),)

        filters = {}
        for field_name, val in six.iteritems(translated_fields):
            if field_name.startswith('master__'):
                filters[field_name[8:]] = val  # avoid translations__master__ back and forth
            else:
                filters["{0}__{1}".format(relname, field_name)] = val

        if len(language_codes) == 1:
            filters[relname + '__language_code'] = language_codes[0]
            return self.filter(**filters)
        else:
            filters[relname + '__language_code__in'] = language_codes
            return self.filter(**filters).distinct()


    def active_translations(self, language_code=None, **translated_fields):
        """
        Only return objects which are translated, or have a fallback that should be displayed.

        Typically that's the currently active language and fallback language.
        When ``hide_untranslated = True``, only the currently active language will be returned.
        """
        # Default:     (language, fallback) when hide_translated == False
        # Alternative: (language,)          when hide_untranslated == True
        language_codes = get_active_language_choices(language_code)
        return self.translated(*language_codes, **translated_fields)


    def iterator(self):
        """
        Overwritten iterator which will apply the decorate functions before returning it.
        """
        # Based on django-queryset-transform.
        # This object however, operates on a per-object instance
        # without breaking the result generators
        base_iterator = super(TranslatableQuerySet, self).iterator()
        for obj in base_iterator:
            # Apply the language setting.
            if self._language:
                obj.set_current_language(self._language)

            yield obj


class TranslatableManager(models.Manager):
    """
    The manager class which ensures the enhanced TranslatableQuerySet object is used.
    """
    queryset_class = TranslatableQuerySet

    def get_query_set(self):
        return self.queryset_class(self.model, using=self._db)

    def language(self, language_code=None):
        """
        Set the language code to assign to objects retrieved using this Manager.
        """
        return self.get_query_set().language(language_code)

    def translated(self, *language_codes, **translated_fields):
        """
        Only return objects which are translated in the given languages.

        NOTE: due to Django `ORM limitations <https://docs.djangoproject.com/en/dev/topics/db/queries/#spanning-multi-valued-relationships>`_,
        this method can't be combined with other filters that access the translated fields. As such, query the fields in one filter:

        .. code-block:: python

            qs.translated('en', name="Cheese Omelette")

        This will query the translated model for the ``name`` field.
        """
        return self.get_query_set().translated(*language_codes, **translated_fields)

    def active_translations(self, language_code=None, **translated_fields):
        """
        Only return objects which are translated, or have a fallback that should be displayed.

        Typically that's the currently active language and fallback language.
        When ``hide_untranslated = True``, only the currently active language will be returned.
        """
        return self.get_query_set().active_translations(language_code, **translated_fields)


# Export the names in django-hvad style too:
TranslationQueryset = TranslatableQuerySet
TranslationManager = TranslatableManager
