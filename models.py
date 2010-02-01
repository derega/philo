# encoding: utf-8
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.contrib.sites.models import Site
import mptt
from utils import fattr
from django.template import add_to_builtins as register_templatetags
from django.template import Template as DjangoTemplate
from django.template import TemplateDoesNotExist
from django.template import Context
from django.core.exceptions import ObjectDoesNotExist
try:
	import json
except ImportError:
	import simplejson as json
from UserDict import DictMixin
from templatetags.containers import ContainerNode
from django.template.loader_tags import ExtendsNode, ConstantIncludeNode, IncludeNode, BlockNode
from django.template.loader import get_template


def _ct_model_name(model):
	opts = model._meta
	while opts.proxy:
		model = opts.proxy_for_model
		opts = model._meta
	return opts.object_name.lower()


class Attribute(models.Model):
	entity_content_type = models.ForeignKey(ContentType, verbose_name='Entity type')
	entity_object_id = models.PositiveIntegerField(verbose_name='Entity ID')
	entity = generic.GenericForeignKey('entity_content_type', 'entity_object_id')
	key = models.CharField(max_length=255)
	json_value = models.TextField(verbose_name='Value (JSON)', help_text='This value must be valid JSON.')
	
	@property
	def value(self):
		return json.loads(self.json_value)
	
	def __unicode__(self):
		return u'"%s": %s' % (self.key, self.value)


class Relationship(models.Model):
	_value_models = []
	
	@staticmethod
	def register_value_model(model):
		if issubclass(model, models.Model):
			model_name = _ct_model_name(model)
			if model_name not in Relationship._value_models:
				Relationship._value_models.append(model_name)
		else:
			raise TypeError('Relationship.register_value_model only accepts subclasses of django.db.models.Model')
	
	@staticmethod
	def unregister_value_model(model):
		if issubclass(model, models.Model):
			model_name = _ct_model_name(model)
			if model_name in Relationship._value_models:
				Relationship._value_models.remove(model_name)
		else:
			raise TypeError('Relationship.unregister_value_model only accepts subclasses of django.db.models.Model')
	
	entity_content_type = models.ForeignKey(ContentType, related_name='relationship_entity_set', verbose_name='Entity type')
	entity_object_id = models.PositiveIntegerField(verbose_name='Entity ID')
	entity = generic.GenericForeignKey('entity_content_type', 'entity_object_id')
	key = models.CharField(max_length=255)
	value_content_type = models.ForeignKey(ContentType, related_name='relationship_value_set', limit_choices_to={'model__in':_value_models}, verbose_name='Value type')
	value_object_id = models.PositiveIntegerField(verbose_name='Value ID')
	value = generic.GenericForeignKey('value_content_type', 'value_object_id')
	
	def __unicode__(self):
		return u'"%s": %s' % (self.key, self.value)


class QuerySetMapper(object, DictMixin):
	def __init__(self, queryset, passthrough=None):
		self.queryset = queryset
		self.passthrough = passthrough
	def __getitem__(self, key):
		try:
			return queryset.get(key__exact=key)
		except ObjectDoesNotExist:
			if self.passthrough:
				return self.passthrough.__getitem__(key)
			raise KeyError
	def keys(self):
		keys = set(self.queryset.values_list('key', flat=True).distinct())
		if self.passthrough:
			keys += set(self.passthrough.keys())
		return list(keys)


class Entity(models.Model):
	attribute_set = generic.GenericRelation(Attribute, content_type_field='entity_content_type', object_id_field='entity_object_id')
	relationship_set = generic.GenericRelation(Relationship, content_type_field='entity_content_type', object_id_field='entity_object_id')
	
	@property
	def attributes(self):
		return QuerySetMapper(self.attribute_set)
	
	@property
	def relationships(self):
		return QuerySetMapper(self.relationship_set)
	
	class Meta:
		abstract = True


class Collection(models.Model):
	name = models.CharField(max_length=255)
	description = models.TextField(blank=True, null=True)


class CollectionMember(models.Model):
	_value_models = []
	
	@staticmethod
	def register_value_model(model):
		if issubclass(model, models.Model):
			model_name = _ct_model_name(model)
			if model_name not in CollectionMember._value_models:
				CollectionMember._value_models.append(model_name)
		else:
			raise TypeError('CollectionMember.register_value_model only accepts subclasses of django.db.models.Model')
	
	@staticmethod
	def unregister_value_model(model):
		if issubclass(model, models.Model):
			model_name = _ct_model_name(model)
			if model_name in CollectionMember._value_models:
				CollectionMember._value_models.remove(model_name)
		else:
			raise TypeError('CollectionMember.unregister_value_model only accepts subclasses of django.db.models.Model')
	
	collection = models.ForeignKey(Collection, related_name='members')
	index = models.PositiveIntegerField(verbose_name='Index', help_text='This will determine the ordering of the item within the collection. (Optional)', null=True, blank=True)
	member_content_type = models.ForeignKey(ContentType, limit_choices_to={'model__in':_value_models}, verbose_name='Member type')
	member_object_id = models.PositiveIntegerField(verbose_name='Member ID')
	member = generic.GenericForeignKey('member_content_type', 'member_object_id')


def register_value_model(model):
	Relationship.register_value_model(model)
	CollectionMember.register_value_model(model)


def unregister_value_model(model):
	Relationship.unregister_value_model(model)
	CollectionMember.unregister_value_model(model)


class TreeManager(models.Manager):
	use_for_related_fields = True
	
	def roots(self):
		return self.filter(parent__isnull=True)
	
	def get_with_path(self, path, root=None, pathsep='/'):
		slugs = path.split(pathsep)
		obj = root
		for slug in slugs:
			if slug: # ignore blank slugs, handles for multiple consecutive pathseps
				try:
					obj = self.get(slug__exact=slug, parent__exact=obj)
				except self.model.DoesNotExist:
					obj = None
					break
		if obj:
			return obj
		raise self.model.DoesNotExist('%s matching query does not exist.' % self.model._meta.object_name)


class TreeModel(models.Model):
	objects = TreeManager()
	parent = models.ForeignKey('self', related_name='children', null=True, blank=True)
	slug = models.SlugField()
	
	def get_path(self, pathsep='/', field='slug'):
		path = getattr(self, field)
		parent = self.parent
		while parent:
			path = getattr(parent, field) + pathsep + path
			parent = parent.parent
		return path
	path = property(get_path)
	
	def __unicode__(self):
		return self.path
	
	class Meta:
		abstract = True


class TreeEntity(TreeModel, Entity):
	@property
	def attributes(self):
		if self.parent:
			return QuerySetMapper(self.attribute_set, passthrough=self.parent.attributes)
		return super(Entity, self).attributes()
	
	@property
	def relationships(self):
		if self.parent:
			return QuerySetMapper(self.relationship_set, passthrough=self.parent.relationships)
		return super(Entity, self).relationships()
	
	class Meta:
		abstract = True


class Template(TreeModel):
	name = models.CharField(max_length=255)
	documentation = models.TextField(null=True, blank=True)
	mimetype = models.CharField(max_length=255, null=True, blank=True)
	code = models.TextField()
	
	@property
	def origin(self):
		return 'philo.models.Template: ' + self.path
	
	@property
	def django_template(self):
		return DjangoTemplate(self.code)
	
	@property
	def containers(self):
		"""
		Returns a list of names of contentlets referenced by containers. 
		This will break if there is a recursive extends or includes in the template code.
		Due to the use of an empty Context, any extends or include tags with dynamic arguments probably won't work.
		"""
		def container_node_names(template):
			def nodelist_container_node_names(nodelist):
				names = []
				for node in nodelist:
					try:
						if isinstance(node, ContainerNode):
							names.append(node.name)
						elif isinstance(node, ExtendsNode):
							names.extend(nodelist_container_node_names(node.nodelist))
							extended_template = node.get_parent(Context())
							if extended_template:
								names.extend(container_node_names(extended_template))
						elif isinstance(node, ConstantIncludeNode):
							included_template = node.template
							if included_template:
								names.extend(container_node_names(included_template))
						elif isinstance(node, IncludeNode):
							included_template = get_template(node.template_name.resolve(Context()))
							if included_template:
								names.extend(container_node_names(included_template))
						elif isinstance(node, BlockNode):
							names.extend(nodelist_container_node_names(node.nodelist))
					except:
						pass # fail for this node
				return names
			return nodelist_container_node_names(template.nodelist)
		return set(container_node_names(self.django_template))
	
	def __unicode__(self):
		return self.get_path(u' › ', 'name')
	
	@staticmethod
	@fattr(is_usable=True)
	def loader(template_name, template_dirs=None): # load_template_source
		try:
			template = Template.objects.get_with_path(template_name)
		except Template.DoesNotExist:
			raise TemplateDoesNotExist(template_name)
		return (template.code, template.origin)
mptt.register(Template)


class Page(TreeEntity):
	template = models.ForeignKey(Template, related_name='pages')
	title = models.CharField(max_length=255)
	
	def __unicode__(self):
		return self.get_path(u' › ', 'title')
mptt.register(Page)


# the following line enables the selection of a page as the root for a given django.contrib.sites Site object
models.ForeignKey(Page, related_name='sites', null=True, blank=True).contribute_to_class(Site, 'root_page')


class Contentlet(models.Model):
	page = models.ForeignKey(Page, related_name='contentlets')
	name = models.CharField(max_length=255)
	content = models.TextField()
	dynamic = models.BooleanField(default=False)


register_templatetags('philo.templatetags.containers')


register_value_model(User)
register_value_model(Group)
register_value_model(Site)
register_value_model(Collection)
register_value_model(Template)
register_value_model(Page)
