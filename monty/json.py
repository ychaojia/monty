"""
JSON serialization and deserialization utilities.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2014, The Materials Virtual Lab"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "1/24/14"

import json
import datetime

from abc import ABCMeta, abstractmethod


try:
    import numpy as np
except ImportError:
    np = None


class MSONable(object):
    """
    This is an abstract base class specifying an API for msonable objects. MSON
    is Monty JSON. Essentially, MSONable objects must implement an as_dict
    method, which must return a json serializable dict and must also support
    no arguments (though optional arguments to finetune the output is ok),
    and a from_dict class method that regenerates the object from the dict
    generated by the as_dict method. The as_dict method should add the
    "@module" and "@class" keys which will allow the MontyEncoder to
    dynamically deserialize the class. E.g.::

        d["@module"] = self.__class__.__module__
        d["@module"] = self.__class__.__name__

    If you use MontyDecoder, these fields will automatically be added.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def as_dict(self):
        """
        A JSON serializable dict representation of an object.
        """
        pass

    @classmethod
    def from_dict(cls, d):
        """
        This implements a default from_dict method which supports all
        classes that simply saves all init arguments in a "init_args"
        key. Otherwise, the MSONAble class must override this class method.
        """
        if "init_args" in d:
            return cls(**d['init_args'])
        raise MSONError("Invalid dict for default from_dict. Please "
                        "override from_dict for ".format(cls))

    def to_json(self):
        """
        Returns a json string representation of the MSONable object.
        """
        return json.dumps(self, cls=MontyEncoder)


class MontyEncoder(json.JSONEncoder):
    """
    A Json Encoder which supports the MSONable API, plus adds support for
    numpy arrays and

    Usage:
        Add it as a *cls* keyword when using json.dump
        json.dumps(object, cls=MontyEncoder)
    """

    def default(self, o):
        """
        Overriding default method for JSON encoding. This method does two
        things: (a) If an object has a to_dict property, return the to_dict
        output. (b) If the @module and @class keys are not in the to_dict,
        add them to the output automatically. If the object has no to_dict
        property, the default Python json encoder default method is called.

        Args:
            o: Python object.

        Return:
            Python dict representation.
        """
        if isinstance(o, datetime.datetime):
            return {"@module": "datetime", "@class": "datetime",
                    "string": str(o)}
        elif np is not None:
            if isinstance(o, np.ndarray):
                return {"@module": "numpy",
                        "@class": "array",
                        "dtype": str(o.dtype),
                        "data": o.tolist()}
            elif isinstance(o, np.generic):
                return o.item()

        try:
            d = o.as_dict()
            if "@module" not in d:
                d["@module"] = o.__class__.__module__
            if "@class" not in d:
                d["@class"] = o.__class__.__name__
            return d
        except AttributeError:
            return json.JSONEncoder.default(self, o)


class MontyDecoder(json.JSONDecoder):
    """
    A Json Decoder which supports the MSONable API. By default, the
    decoder attempts to find a module and name associated with a dict. If
    found, the decoder will generate a Pymatgen as a priority.  If that fails,
    the original decoded dictionary from the string is returned. Note that
    nested lists and dicts containing pymatgen object will be decoded correctly
    as well.

    Usage:
        Add it as a *cls* keyword when using json.load
        json.loads(json_string, cls=MontyDecoder)
    """

    def process_decoded(self, d):
        """
        Recursive method to support decoding dicts and lists containing
        pymatgen objects.
        """
        if isinstance(d, dict):
            if "@module" in d and "@class" in d:
                modname = d["@module"]
                classname = d["@class"]
            else:
                modname = None
                classname = None
            if modname:
                if modname == "datetime" and classname == "datetime":
                    try:
                        dt = datetime.datetime.strptime(d["string"],
                                                        "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        dt = datetime.datetime.strptime(d["string"],
                                                        "%Y-%m-%d %H:%M:%S")
                    return dt
                elif modname == "numpy" and classname == "array":
                    return np.array(d["data"], dtype=d["dtype"])

                mod = __import__(modname, globals(), locals(), [classname], 0)
                if hasattr(mod, classname):
                    cls_ = getattr(mod, classname)
                    data = {k: v for k, v in d.items()
                            if k not in ["@module", "@class"]}
                    if hasattr(cls_, "from_dict"):
                        return cls_.from_dict(data)
            return {self.process_decoded(k): self.process_decoded(v)
                    for k, v in d.items()}
        elif isinstance(d, list):
            return [self.process_decoded(x) for x in d]

        return d

    def decode(self, *args, **kwargs):
        d = json.JSONDecoder.decode(self, *args, **kwargs)
        return self.process_decoded(d)


class MSONError(Exception):
    """
    Exception class for serialization errors.
    """
    pass
