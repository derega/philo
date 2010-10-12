from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils import simplejson as json
from django.core.exceptions import ObjectDoesNotExist
from philo.exceptions import AncestorDoesNotExist
from philo.models.fields import JSONField
from philo.utils import ContentTypeRegistryLimiter
from philo.signals import entity_class_prepared
from philo.validators import json_validator
from UserDict import DictMixin


class Tag(models.Model):
	name = models.CharField(max_length=255)
	slug = models.SlugField(max_length=255, unique=True)
	
	def __unicode__(self):
		return self.name
	
	class Meta:
		app_label = 'philo'


class Titled(models.Model):
	title = models.CharField(max_length=255)
	slug = models.SlugField(max_length=255)
	
	def __unicode__(self):
		return self.title
	
	class Meta:
		abstract = True


value_content_type_limiter = ContentTypeRegistryLimiter()


def register_value_model(model):
	value_content_type_limiter.register_class(model)


def unregister_value_model(model):
	value_content_type_limiter.unregister_class(model)


class JSONValue(models.Model):
	value = JSONField() #verbose_name='Value (JSON)', help_text='This value must be valid JSON.')
	
	def __unicode__(self):
		return self.value_json
	
	class Meta:
		app_label = 'philo'


class ForeignKeyValue(models.Model):
	content_type = models.ForeignKey(ContentType, related_name='foreign_key_value_set', limit_choices_to=value_content_type_limiter, verbose_name='Value type', null=True, blank=True)
	object_id = models.PositiveIntegerField(verbose_name='Value ID', null=True, blank=True)
	value = generic.GenericForeignKey()
	
	def __unicode__(self):
		return unicode(self.value)
	
	class Meta:
		app_label = 'philo'


class ManyToManyValue(models.Model):
	content_type = models.ForeignKey(ContentType, related_name='many_to_many_value_set', limit_choices_to=value_content_type_limiter, verbose_name='Value type', null=True, blank=True)
	object_ids = models.CommaSeparatedIntegerField(max_length=300, verbose_name='Value IDs', null=True, blank=True)
	
	def get_value(self):
		return self.content_type.model_class()._default_manager.filter(id__in=self.object_ids)
	
	def set_value(self, value):
		if not isinstance(value, models.query.QuerySet):
			raise TypeError("Value must be a QuerySet.")
		self.content_type = ContentType.objects.get_for_model(value.model)
		self.object_ids = ','.join(value.values_list('id', flat=True))
	
	value = property(get_value, set_value)
	
	def __unicode__(self):
		return unicode(self.value)
	
	class Meta:
		app_label = 'philo'


attribute_value_limiter = ContentTypeRegistryLimiter()
attribute_value_limiter.register_class(JSONValue)
attribute_value_limiter.register_class(ForeignKeyValue)
attribute_value_limiter.register_class(ManyToManyValue)


class Attribute(models.Model):
	entity_content_type = models.ForeignKey(ContentType, related_name='attribute_entity_set', verbose_name='Entity type')
	entity_object_id = models.PositiveIntegerField(verbose_name='Entity ID')
	entity = generic.GenericForeignKey('entity_content_type', 'entity_object_id')
	
	value_content_type = models.ForeignKey(ContentType, related_name='attribute_value_set', limit_choices_to=attribute_value_limiter, verbose_name='Value type', null=True, blank=True)
	value_object_id = models.PositiveIntegerField(verbose_name='Value ID', null=True, blank=True)
	value = generic.GenericForeignKey('value_content_type', 'value_object_id')
	
	key = models.CharField(max_length=255)
	
	def get_value_class(self, value):
		if isinstance(value, models.query.QuerySet):
			return ManyToManyValue
		elif isinstance(value, models.Model):
			return ForeignKeyValue
		else:
			return JSONValue
	
	def set_value(self, value):
		value_class = self.get_value_class(value)
		
		if self.value is None or value_class != self.value_content_type.model_class():
			if self.value is not None:
				self.value.delete()
			new_value = value_class()
			new_value.value = value
			new_value.save()
			self.value = new_value
		else:
			self.value.value = value
			self.value.save()
	
	def __unicode__(self):
		return u'"%s": %s' % (self.key, self.value)
	
	class Meta:
		app_label = 'philo'
		unique_together = (('key', 'entity_content_type', 'entity_object_id'), ('value_content_type', 'value_object_id'))


class QuerySetMapper(object, DictMixin):
	def __init__(self, queryset, passthrough=None):
		self.queryset = queryset
		self.passthrough = passthrough
	
	def __getitem__(self, key):
		try:
			return self.queryset.get(key__exact=key).value
		except ObjectDoesNotExist:
			if self.passthrough is not None:
				return self.passthrough.__getitem__(key)
			raise KeyError
	
	def keys(self):
		keys = set(self.queryset.values_list('key', flat=True).distinct())
		if self.passthrough is not None:
			keys |= set(self.passthrough.keys())
		return list(keys)


class EntityOptions(object):
	def __init__(self, options):
		if options is not None:
			for key, value in options.__dict__.items():
				setattr(self, key, value)
		if not hasattr(self, 'proxy_fields'):
			self.proxy_fields = []
	
	def add_proxy_field(self, proxy_field):
		self.proxy_fields.append(proxy_field)


class EntityBase(models.base.ModelBase):
	def __new__(cls, name, bases, attrs):
		new = super(EntityBase, cls).__new__(cls, name, bases, attrs)
		entity_options = attrs.pop('EntityMeta', None)
		setattr(new, '_entity_meta', EntityOptions(entity_options))
		entity_class_prepared.send(sender=new)
		return new


class Entity(models.Model):
	__metaclass__ = EntityBase
	
	attribute_set = generic.GenericRelation(Attribute, content_type_field='entity_content_type', object_id_field='entity_object_id')
	
	@property
	def attributes(self):
		return QuerySetMapper(self.attribute_set)
	
	@property
	def _added_attribute_registry(self):
		if not hasattr(self, '_real_added_attribute_registry'):
			self._real_added_attribute_registry = {}
		return self._real_added_attribute_registry
	
	@property
	def _removed_attribute_registry(self):
		if not hasattr(self, '_real_removed_attribute_registry'):
			self._real_removed_attribute_registry = []
		return self._real_removed_attribute_registry
	
	def save(self, *args, **kwargs):
		super(Entity, self).save(*args, **kwargs)
		
		for key in self._removed_attribute_registry:
			self.attribute_set.filter(key__exact=key).delete()
		del self._removed_attribute_registry[:]
		
		for key, value in self._added_attribute_registry.items():
			try:
				attribute = self.attribute_set.get(key__exact=key)
			except Attribute.DoesNotExist:
				attribute = Attribute()
				attribute.entity = self
				attribute.key = key
			attribute.set_value(value)
			attribute.save()
		self._added_attribute_registry.clear()
	
	class Meta:
		abstract = True


class TreeManager(models.Manager):
	use_for_related_fields = True
	
	def roots(self):
		return self.filter(parent__isnull=True)
	
	def get_with_path(self, path, root=None, absolute_result=True, pathsep='/'):
		"""
		Returns the object with the path, or None if there is no object with that path,
		unless absolute_result is set to False, in which case it returns a tuple containing
		the deepest object found along the path, and the remainder of the path after that
		object as a string (or None in the case that there is no remaining path).
		"""
		slugs = path.split(pathsep)
		obj = root
		remaining_slugs = list(slugs)
		remainder = None
		for slug in slugs:
			remaining_slugs.remove(slug)
			if slug: # ignore blank slugs, handles for multiple consecutive pathseps
				try:
					obj = self.get(slug__exact=slug, parent__exact=obj)
				except self.model.DoesNotExist:
					if absolute_result:
						obj = None
					remaining_slugs.insert(0, slug)
					remainder = pathsep.join(remaining_slugs)
					break
		if obj:
			if absolute_result:
				return obj
			else:
				return (obj, remainder)
		raise self.model.DoesNotExist('%s matching query does not exist.' % self.model._meta.object_name)


class TreeModel(models.Model):
	objects = TreeManager()
	parent = models.ForeignKey('self', related_name='children', null=True, blank=True)
	slug = models.SlugField(max_length=255)
	
	def has_ancestor(self, ancestor):
		parent = self
		while parent:
			if parent == ancestor:
				return True
			parent = parent.parent
		return False
	
	def get_path(self, root=None, pathsep='/', field='slug'):
		if root is not None:
			if not self.has_ancestor(root):
				raise AncestorDoesNotExist(root)
			path = ''
			parent = self
			while parent and parent != root:
				path = getattr(parent, field, '?') + pathsep + path
				parent = parent.parent
			return path
		else:
			path = getattr(self, field, '?')
			parent = self.parent
			while parent and parent != root:
				path = getattr(parent, field, '?') + pathsep + path
				parent = parent.parent
			return path
	path = property(get_path)
	
	def __unicode__(self):
		return self.path
	
	class Meta:
		unique_together = (('parent', 'slug'),)
		abstract = True


class TreeEntity(Entity, TreeModel):
	@property
	def attributes(self):
		if self.parent:
			return QuerySetMapper(self.attribute_set, passthrough=self.parent.attributes)
		return super(TreeEntity, self).attributes
	
	@property
	def relationships(self):
		if self.parent:
			return QuerySetMapper(self.relationship_set, passthrough=self.parent.relationships)
		return super(TreeEntity, self).relationships
	
	class Meta:
		abstract = True