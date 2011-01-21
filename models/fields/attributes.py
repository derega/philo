"""
The Attributes defined in this file can be assigned as fields on a proxy of
a subclass of philo.models.Entity. They act like any other model fields,
but instead of saving their data to the database, they save it to
attributes related to a model instance. Additionally, a new attribute will
be created for an instance if and only if the field's value has been set.
This is relevant i.e. for passthroughs, where the value of the field may
be defined by some other instance's attributes.

Example::

	class Thing(Entity):
		numbers = models.PositiveIntegerField()
	
	class ThingProxy(Thing):
		improvised = JSONAttribute(models.BooleanField)
		
		class Meta:
			proxy = True
"""
from django import forms
from django.core.exceptions import FieldError
from django.db import models
from django.db.models.fields import NOT_PROVIDED
from django.utils.text import capfirst
from philo.signals import entity_class_prepared


__all__ = ('JSONAttribute', 'ForeignKeyAttribute', 'ManyToManyAttribute')


ATTRIBUTE_REGISTRY = '_attribute_registry'


class EntityProxyField(object):
	def __init__(self, verbose_name=None, help_text=None, default=NOT_PROVIDED, editable=True, *args, **kwargs):
		self.verbose_name = verbose_name
		self.help_text = help_text
		self.default = default
		self.editable = editable
	
	def actually_contribute_to_class(self, sender, **kwargs):
		sender._entity_meta.add_proxy_field(self)
	
	def contribute_to_class(self, cls, name):
		from philo.models.base import Entity
		if issubclass(cls, Entity):
			self.name = name
			self.model = cls
			if self.verbose_name is None and name:
				self.verbose_name = name.replace('_', ' ')
			entity_class_prepared.connect(self.actually_contribute_to_class, sender=cls)
		else:
			raise FieldError('%s instances can only be declared on Entity subclasses.' % self.__class__.__name__)
	
	def formfield(self, form_class=forms.CharField, **kwargs):
		defaults = {
			'required': False,
			'label': capfirst(self.verbose_name),
			'help_text': self.help_text
		}
		if self.has_default():
			defaults['initial'] = self.default
		defaults.update(kwargs)
		return form_class(**defaults)
	
	def value_from_object(self, obj):
		return getattr(obj, self.name)
	
	def has_default(self):
		return self.default is not NOT_PROVIDED


class AttributeFieldDescriptor(object):
	def __init__(self, field):
		self.field = field
	
	def get_registry(self, instance):
		if ATTRIBUTE_REGISTRY not in instance.__dict__:
			instance.__dict__[ATTRIBUTE_REGISTRY] = {'added': set(), 'removed': set()}
		return instance.__dict__[ATTRIBUTE_REGISTRY]
	
	def __get__(self, instance, owner):
		if instance is None:
			return self
		
		if self.field.name not in instance.__dict__:
			instance.__dict__[self.field.name] = instance.attributes[self.field.attribute_key]
		
		return instance.__dict__[self.field.name]
	
	def __set__(self, instance, value):
		if instance is None:
			raise AttributeError("%s must be accessed via instance" % self.field.name)
		
		self.field.validate_value(value)
		instance.__dict__[self.field.name] = value
		
		registry = self.get_registry(instance)
		registry['added'].add(self.field)
		registry['removed'].remove(self.field)
	
	def __delete__(self, instance):
		del instance.__dict__[self.field.name]
		
		registry = self.get_registry(instance)
		registry['added'].remove(self.field)
		registry['removed'].add(self.field)


def process_attribute_fields(sender, instance, created, **kwargs):
	if ATTRIBUTE_REGISTRY in instance.__dict__:
		registry = instance.__dict__[ATTRIBUTE_REGISTRY]
		instance.attribute_set.filter(key__in=[field.attribute_key for field in registry['removed']]).delete()
		
		from philo.models import Attribute
		for field in registry['added']:
			try:
				attribute = self.attribute_set.get(key=field.key)
			except Attribute.DoesNotExist:
				attribute = Attribute()
				attribute.entity = instance
				attribute.key = field.key
			
			value_class = field.get_value_class()
			if isinstance(attribute.value, value_class):
				value = attribute.value
			else:
				if isinstance(attribute.value, models.Model):
					attribute.value.delete()
				value = value_class()
			
			value.set_value(field.value_from_object(instance))
			value.save()
			
			attribute.value = value
			attribute.save()
		del instance.__dict__[ATTRIBUTE_REGISTRY]


class AttributeField(EntityProxyField):
	def __init__(self, attribute_key=None, **kwargs):
		self.attribute_key = attribute_key
		super(AttributeField, self).__init__(**kwargs)
	
	def actually_contribute_to_class(self, sender, **kwargs):
		super(AttributeField, self).actually_contribute_to_class(sender, **kwargs)
		setattr(sender, self.name, AttributeFieldDescriptor(self))
		opts = sender._entity_meta
		if not hasattr(opts, '_has_attribute_fields'):
			opts._has_attribute_fields = True
			models.signals.post_save.connect(process_attribute_fields, sender=sender)
		
	
	def contribute_to_class(self, cls, name):
		if self.attribute_key is None:
			self.attribute_key = name
		super(AttributeField, self).contribute_to_class(cls, name)
	
	def validate_value(self, value):
		"Confirm that the value is valid or raise an appropriate error."
		raise NotImplementedError("validate_value must be implemented by AttributeField subclasses.")
	
	def get_value_class(self):
		raise NotImplementedError("get_value_class must be implemented by AttributeField subclasses.")


class JSONAttribute(AttributeField):
	def __init__(self, field_template=None, **kwargs):
		super(JSONAttribute, self).__init__(**kwargs)
		if field_template is None:
			field_template = models.CharField(max_length=255)
		self.field_template = field_template
	
	def validate_value(self, value):
		pass
	
	def formfield(self, **kwargs):
		defaults = {
			'required': False,
			'label': capfirst(self.verbose_name),
			'help_text': self.help_text
		}
		if self.has_default():
			defaults['initial'] = self.default
		defaults.update(kwargs)
		return self.field_template.formfield(**defaults)
	
	def get_value_class(self):
		from philo.models import JSONValue
		return JSONValue
	
	# Not sure what this is doing - keep eyes open!
	#def value_from_object(self, obj):
	#	try:
	#		return getattr(obj, self.name)
	#	except AttributeError:
	#		return None


class ForeignKeyAttribute(AttributeField):
	def __init__(self, model, limit_choices_to=None, **kwargs):
		super(ForeignKeyAttribute, self).__init__(**kwargs)
		self.model = model
		if limit_choices_to is None:
			limit_choices_to = {}
		self.limit_choices_to = limit_choices_to
	
	def validate_value(self, value):
		if value is not None and not isinstance(value, self.model) :
			raise TypeError("The '%s' attribute can only be set to an instance of %s or None." % (self.name, self.model.__name__))
	
	def formfield(self, form_class=forms.ModelChoiceField, **kwargs):
		defaults = {
			'queryset': self.model._default_manager.complex_filter(self.limit_choices_to)
		}
		defaults.update(kwargs)
		return super(ForeignKeyAttribute, self).formfield(form_class=form_class, **defaults)
	
	def get_value_class(self):
		from philo.models import ForeignKeyValue
		return ForeignKeyValue
	
	#def value_from_object(self, obj):
	#	try:
	#		relobj = super(ForeignKeyAttribute, self).value_from_object(obj)
	#	except AttributeError:
	#		return None
	#	return getattr(relobj, 'pk', None)


class ManyToManyAttribute(ForeignKeyAttribute):
	def validate_value(self, value):
		if not isinstance(value, models.query.QuerySet) or value.model != self.model:
			raise TypeError("The '%s' attribute can only be set to a %s QuerySet." % (self.name, self.model.__name__))
	
	def formfield(self, form_class=forms.ModelMultipleChoiceField, **kwargs):
		return super(ManyToManyAttribute, self).formfield(form_class=form_class, **kwargs)
	
	def get_value_class(self):
		from philo.models import ManyToManyValue
		return ManyToManyValue