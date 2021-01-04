import collections.abc
import numbers

from octue import exceptions


IS_FILTER_ACTIONS = {
    "is": lambda item, filter_value: item is filter_value,
    "is_not": lambda item, filter_value: item is not filter_value,
}

EQUALS_FILTER_ACTION = {"equals": lambda item, filter_value: filter_value == item}

CONTAINS_FILTER_ACTIONS = {
    "contains": lambda item, filter_value: filter_value in item,
    "not_contains": lambda item, filter_value: filter_value not in item,
}


# Filters for specific types e.g. list or int.
TYPE_FILTERS = {
    "bool": IS_FILTER_ACTIONS,
    "str": {
        "icontains": lambda item, filter_value: filter_value.lower() in item.lower(),
        "ends_with": lambda item, filter_value: item.endswith(filter_value),
        "starts_with": lambda item, filter_value: item.startswith(filter_value),
        **EQUALS_FILTER_ACTION,
        **IS_FILTER_ACTIONS,
        **CONTAINS_FILTER_ACTIONS,
    },
    "NoneType": IS_FILTER_ACTIONS,
    "TagGroup": {
        "starts_with": lambda item, filter_value: item.starts_with(filter_value),
        "ends_with": lambda item, filter_value: item.ends_with(filter_value),
        **EQUALS_FILTER_ACTION,
        **CONTAINS_FILTER_ACTIONS,
        **IS_FILTER_ACTIONS,
    },
}

# Filters for interfaces e.g. iterables or numbers.
INTERFACE_FILTERS = {
    numbers.Number: {
        "lt": lambda item, filter_value: item < filter_value,
        "lte": lambda item, filter_value: item <= filter_value,
        "gt": lambda item, filter_value: item > filter_value,
        "gte": lambda item, filter_value: item >= filter_value,
        **EQUALS_FILTER_ACTION,
        **IS_FILTER_ACTIONS,
    },
    collections.abc.Iterable: {**EQUALS_FILTER_ACTION, **CONTAINS_FILTER_ACTIONS, **IS_FILTER_ACTIONS},
}


class Filterable:
    def satisfies(self, filter_name, filter_value):
        """ Check that the instance satisfies the given filter for the given filter value. """
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
            return self._get_filter_actions_for_attribute(attribute)[filter_action]

        except KeyError as error:
            attribute_type = type(attribute)
            raise exceptions.InvalidInputException(
                f"There is no filter called {error.args[0]!r} for attributes of type {attribute_type}. The options "
                f"are {self._get_filter_actions_for_attribute(attribute).keys()!r}"
            )

    def _get_filter_actions_for_attribute(self, attribute):
        """ Get the possible filters for the given attribute based on its type or interface, raising an error if the
        attribute's type isn't supported (i.e. if there aren't any filters defined for it)."""
        try:
            return TYPE_FILTERS[type(attribute).__name__]

        except KeyError as error:
            # This allows handling of objects that conform to a certain interface (e.g. iterables) without needing the
            # specific type.
            for type_ in INTERFACE_FILTERS:
                if not isinstance(attribute, type_):
                    continue
                return INTERFACE_FILTERS[type_]

            raise exceptions.InvalidInputException(
                f"Attributes of type {error.args[0]} are not currently supported for filtering."
            )
