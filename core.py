import copy
import merge
import re
import os

def encode_filename(name):
    name = name.decode()
    return re.sub('[^\w-]+', '', name.lower().replace(' ','-')) + '.dfmod'
    
def path_to_filename(path):
    return os.path.split(path)[-1]

class DataSet(object):
    def __init__(self, objects, included_files=[]):
        self.objects = objects
        self.included_files = included_files
        self.objects_map = {}
        for object in self.objects:
            self.objects_map[object.root_type + object.type + object.name] = object
        
    def get_object(self, root_type, _type, name):
        key = root_type + _type + name
        if key not in self.objects_map:
            print(key)
            return None
        return self.objects_map[key]
        
    def add_object(self, object):
        self.objects.append(object)
        self.objects_map[object.root_type + object.type + object.name] = object
        

    
            
    def apply_mod(self, mod, merge_changes=True, partial_merge=False, delete_override=False):
        core_dataset = mod.base
        for object in mod.added_objects:
            self.add_object(copy.copy(object))
        for object in mod.modified_objects:
            current_object = self.get_object(object.root_type, object.type, object.name)
            core_object = core_dataset.get_object(object.root_type, object.type, object.name)
            if not current_object:
                print(('Failed to apply edits to [%s:%s] from mod %s because the object does not exist' % (object.type, object.name, mod.name)))
                continue
            if current_object.deleted:
                print(('Failed to apply edits to [%s:%s] from mod %s due to prior deletion' % (object.type, object.name, mod.name)))
                continue
            if not current_object.modified:
                current_object.extra_data = object.extra_data
                current_object.modified = True
            elif merge_changes:
                result = merge.merge_data(core_object.extra_data, current_object.extra_data, object.extra_data)
                if result[1]:
                    current_object.extra_data = result[0]
                    current_object.modified = True
                    print(('Merged edit to [%s:%s] from mod %s with prior edits' % (object.type, object.name, mod.name)))
                else:
                    if partial_merge:
                        current_object.extra_data = result[0]
                        current_object.modified = True
                        print(('Merged edit to [%s:%s] from mod %s with prior edits (Note: merge was partial)' % (object.type, object.name, mod.name)))
                    else:
                        print(('Failed to merge edit to [%s:%s] from mod "%s" due to prior edit (Partial merges are disabled)' % (object.type, object.name, mod.name)))
            else:
                print(('Failed to apply edits to [%s:%s] from mod %s due to prior edit (Merges are disabled)' % (object.type, object.name, mod.name)))
        for object in mod.deleted_objects:
            current_object = self.get_object(object.root_type, object.type, object.name)
            if not current_object or current_object not in self.objects: # Already deleted, don't worry about it
                continue
            if not current_object.modified:
                current_object.deleted = True
                self.objects.remove(current_object)
            elif delete_override:
                current_object.deleted = True
                self.objects.remove(current_object)
                print(('Applied deletion of [%s:%s] from mod "%s", overriding prior edit' % (object.type, object.name, mod.name)))
            else:
                print(('Failed to apply deletion of [%s:%s] from mod "%s" due to prior edit' % (object.type, object.name, mod.name)))
            
    def apply_mod_for_editing(self, mod):
        for object in mod.objects:
            current_object = self.get_object(object.root_type, object.type, object.name)
            if current_object:
                self.objects.remove(current_object)
            self.objects.append(object)
            
    def difference(self, other):
        ''' Returns a list of objects corresponding to the changes made by the given dataset'''
        my_objects = set(self.objects)
        other_objects = set(other.objects)
        other_filenames = set([o.file_name for o in other.objects])
        changes = []
        for object in other.objects: # Added
            if object not in my_objects:
                o = copy.deepcopy(object)
                o.added = True
                changes.append(o)
        for object in my_objects - other_objects: # Deleted
            if object.file_name not in other.included_files:
                continue # If the other set doesn't have the core file, assume it should be kept
            o = copy.deepcopy(object)
            o.deleted = True
            changes.append(o)
        for object in my_objects:
            other_object = other.get_object(object.root_type, object.type, object.name)
            if other_object and object.extra_data != other_object.extra_data:
                o = copy.deepcopy(object)
                o.modified = True
                o.extra_data = other_object.extra_data
                changes.append(o)
        return changes
    
    def strip_object_status(self):
        ''' Removes the indicators on each object that track whether it has been
        added, edited, or deleted. Used when modifying bases for metamods'''
        new_objects = []
        for object in self.objects:
            if object.added or object.modified or object.deleted:
                new_object = copy.copy(object)
                new_object.added = False
                new_object.modified = False
                new_object.deleted = False
                new_objects.append(new_object)
            else:
                new_objects.append(object)
        self.objects = new_objects
    
    def checksum(self):
        s = sum([hash(o.name + o.extra_data) for o in self.objects])
        return hash(s)

class Mod(object):
    ''' A mod object stores only the objects it changes..'''
    def __init__(self, name, path, base, objects, parent=None):
        self.name = name.encode('utf-8') # Make sure name is a string to be usable in keyss
        self.path = path
        self.base = base
        self.objects = objects
        self.parent = parent
        
    @property
    def changed_objects(self):
        return [o for o in self.objects if o.added or o.modified or o.deleted]
        
    @property
    def added_objects(self):
        return [o for o in self.objects if o.added]
        
    @property
    def modified_objects(self):
        return [o for o in self.objects if o.modified]
        
    @property
    def deleted_objects(self):
        return [o for o in self.objects if o.deleted]
        
    @property
    def meta(self):
        return self.parent is not None
    
    def checksum(self):
        s = sum([hash(o.name + o.extra_data) for o in self.objects])
        return hash(s)
    
    def __str__(self):
        return '%s\nA:%s\nM:%s\nD:%s' % (self.name, self.added_objects, self.modified_objects, self.deleted_objects)

  

class Object(object):
    def __init__(self, file_name, type, root_type, name):
        self.file_name = file_name
        self.type = type
        self.root_type = root_type
        self.name = name
        self.tags = []
        self.extra_data = ''
        self.patch_cache = None
        
        self.added = False
        self.modified = False
        self.deleted = False
        
    def add_tag(self, tag):
        self.tags.append(tag)
    def add_data(self, data):
        self.extra_data += data
        
    def invalidate_cache(self):
        self.patch_cache = None
        
    def __repr__(self):
        return '%s:%s' % (self.type, self.name)
        
    def __eq__(self, other):
        return self.type == other.type and self.name == other.name
    
    def __hash__(self):
        return hash(self.type + self.name)
        


