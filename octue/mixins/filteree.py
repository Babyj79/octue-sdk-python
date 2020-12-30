import collections.abc
import numbers

from octue import exceptions


NONE_FILTERS_FOR_NON_NONES = {"is_none": lambda item, filter_value: False, "not_none": lambda item, filter_value: True}

FILTERS = {
    bool: {"is": lambda item, filter_value: item is filter_value, **NONE_FILTERS_FOR_NON_NONES},
    str: {
        "icontains": lambda item, filter_value: filter_value.lower() in item.lower(),
        "contains": lambda item, filter_value: filter_value in item,
        "ends_with": lambda item, filter_value: item.endswith(filter_value),
        "starts_with": lambda item, filter_value: item.startswith(filter_value),
        "equals": lambda item, filter_value: filter_value == item,
        **NONE_FILTERS_FOR_NON_NONES,
    },
    type(None): {"is_none": lambda item, filter_value: True, "not_none": lambda item, filter_value: False},
    numbers.Number: {
        "equals": lambda item, filter_value: item == filter_value,
        "lt": lambda item, filter_value: item < filter_value,
        "lte": lambda item, filter_value: item <= filter_value,
        "mt": lambda item, filter_value: item > filter_value,
        "mte": lambda item, filter_value: item >= filter_value,
        **NONE_FILTERS_FOR_NON_NONES,
    },
    collections.abc.Iterable: {
        "contains": lambda item, filter_value: filter_value in item,
        "not_contains": lambda item, filter_value: filter_value not in item,
        "starts_with": lambda item, filter_value: item.starts_with(filter_value),
        "ends_with": lambda item, filter_value: item.ends_with(filter_value),
        **NONE_FILTERS_FOR_NON_NONES,
    },
}


class Filteree:

    _FILTERABLE_ATTRIBUTES = None

    def satisfies(self, filter_name, filter_value):
        """ Check that the instance satisfies the given filter for the given filter value. """
        if self._FILTERABLE_ATTRIBUTES is None:
            raise ValueError(
                "A Filteree should have at least one attribute name in its class-level _FILTERABLE_ATTRIBUTES"
            )

        attribute_name, filter_action = self._split_filter_name(filter_name)
        attribute = getattr(self, attribute_name)
        filter_ = self._get_filter(attribute, filter_action)
        return filter_(attribute, filter_value)

    def _split_filter_name(self, filter_name):
        """ Split the filter name into the attribute name and filter action, raising an error if it the attribute name
        and filter action aren't delimited by a double underscore i.e. "__".
        """
        try:
            attribute_name, filter_action = filter_name.split("__", 1)
        except ValueError:
            raise exceptions.InvalidInputException(
                f"Invalid filter name {filter_name!r}. Filter names should be in the form "
                f"'<attribute_name>__<filter_kind>'."
            )

        return attribute_name, filter_action

    def _get_filter(self, attribute, filter_action):
        """ Get the filter for the attribute and filter action, raising an error if there is no filter action of that
        name.
        """
        try:
            return self._get_filters_for_attribute(attribute)[filter_action]

        except KeyError as error:
            attribute_type = type(attribute)
            raise exceptions.InvalidInputException(
                f"There is no filter called {error.args[0]!r} for attributes of type {attribute_type}. The options "
                f"are {set(FILTERS[attribute_type].keys())!r}"
            )

    def _get_filters_for_attribute(self, attribute):
        """ Get the possible filters for the given attribute based on its type or interface, raising an error if the
        attribute's type isn't supported (i.e. if there aren't any filters defined for it)."""
        try:
            return FILTERS[type(attribute)]

        except KeyError as error:
            # This allows handling of objects that conform to a certain interface (e.g. iterables) without needing the
            # specific type.
            for type_ in FILTERS:
                if not isinstance(attribute, type_):
                    continue
                return FILTERS[type_]

            raise exceptions.InvalidInputException(
                f"Attributes of type {error.args[0]} are not currently supported for filtering."
            )
