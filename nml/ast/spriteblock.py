from nml import expression, generic, global_constants
from nml.actions import action1, action2, action2layout, action2real, real_sprite
from nml.ast import base_statement

class TemplateDeclaration(base_statement.BaseStatement):
    def __init__(self, name, param_list, sprite_list, pos):
        base_statement.BaseStatement.__init__(self, "template declaration", pos, False, False)
        self.name = name
        self.param_list = param_list
        self.sprite_list = sprite_list
    
    def pre_process(self):
        #check that all templates that are referred to exist at this point
        #This prevents circular dependencies
        for sprite in self.sprite_list:
            if isinstance(sprite, real_sprite.TemplateUsage):
                if sprite.name.value == self.name.value:
                    raise generic.ScriptError("Sprite template '%s' includes itself." % sprite.name.value, self.pos)
                elif sprite.name.value not in real_sprite.sprite_template_map:
                    raise generic.ScriptError("Encountered unknown template identifier: " + sprite.name.value, sprite.pos)
        #Register template
        if self.name.value not in real_sprite.sprite_template_map:
            real_sprite.sprite_template_map[self.name.value] = self
        else:
            raise generic.ScriptError("Template named '%s' is already defined, first definition at %s" % (self.name.value, real_sprite.sprite_template_map[self.name.value].pos), self.pos)

    def get_labels(self):
        labels = {}
        offset = 0
        for sprite in self.sprite_list:
            sprite_labels, num_sprites = sprite.get_labels()
            for lbl, lbl_offset in sprite_labels.iteritems():
                if lbl in labels:
                    raise generic.ScriptError("Duplicate label encountered; '%s' already exists." % lbl, self.pos)
                labels[lbl] = lbl_offset + offset
            offset += num_sprites
        return labels, offset

    def debug_print(self, indentation):
        print indentation*' ' + 'Template declaration:', self.name.value
        print (indentation+2)*' ' + 'Parameters:'
        for param in self.param_list:
            param.debug_print(indentation + 4)
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

    def get_action_list(self):
        return []

    def __str__(self):
        ret = "template %s(%s) {\n" % (str(self.name), ", ".join([str(param) for param in self.param_list]))
        for sprite in self.sprite_list:
            ret += "\t%s\n" % str(sprite)
        ret += "}\n"
        return ret

spriteset_base_class = action2.make_sprite_group_class(True, False, True, False, True, cls_is_relocatable = True)

class SpriteSet(spriteset_base_class):
    def __init__(self, param_list, sprite_list, pos):
        base_statement.BaseStatement.__init__(self, "spriteset", pos, False, False)
        if not (1 <= len(param_list) <= 2):
            raise generic.ScriptError("Spriteset requires 1 or 2 parameters, encountered " + str(len(param_list)), pos)
        name = param_list[0]
        if not isinstance(name, expression.Identifier):
            raise generic.ScriptError("Spriteset parameter 1 'name' should be an identifier", name.pos)
        self.initialize(name)
        if len(param_list) >= 2:
            self.pcx = param_list[1].reduce()
            if not isinstance(self.pcx, expression.StringLiteral):
                raise generic.ScriptError("Spriteset-block parameter 2 'file' must be a string literal", self.pcx.pos)
        else:
            self.pcx = None
        self.sprite_list = sprite_list
        self.action1_num = None #set number in action1
        self.labels = {} #mapping of real sprite labels to offsets

    def pre_process(self):
        spriteset_base_class.pre_process(self)
        offset = 0
        for sprite in self.sprite_list:
            sprite_labels, num_sprites = sprite.get_labels()
            for lbl, lbl_offset in sprite_labels.iteritems():
                if lbl in self.labels:
                    raise generic.ScriptError("Duplicate label encountered; '%s' already exists." % lbl, self.pos)
                self.labels[lbl] = lbl_offset + offset
            offset += num_sprites

    def collect_references(self):
        return []

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite set:', self.name.value
        print (indentation+2)*' ' + 'Source:  ', self.pcx.value if self.pcx is not None else 'None'
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

    def get_action_list(self):
        # Warn if spriteset is unused
        self.prepare_output()
        # Actions are created when parsing the action2s, not here
        return []

    def __str__(self):
        filename = (", " + str(self.pcx)) if self.pcx is not None else ""
        ret = "spriteset(%s%s) {\n" % (self.name, filename)
        for sprite in self.sprite_list:
            ret += "\t%s\n" % str(sprite)
        ret += "}\n"
        return ret

spritegroup_base_class = action2.make_sprite_group_class(False, True, True, False)

class SpriteGroup(spritegroup_base_class):
    def __init__(self, name, spriteview_list, pos = None):
        base_statement.BaseStatement.__init__(self, "spritegroup", pos, False, False)
        self.initialize(name)
        self.spriteview_list = spriteview_list

    # pre_process is defined by the base class
    def pre_process(self):
        for spriteview in self.spriteview_list:
            spriteview.pre_process()
        spritegroup_base_class.pre_process(self)

    def collect_references(self):
        all_sets = []
        for spriteview in self.spriteview_list:
            all_sets.extend(spriteview.spriteset_list)
        return all_sets

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite group:', self.name.value
        for spriteview in self.spriteview_list:
            spriteview.debug_print(indentation + 2)

    def get_action_list(self):
        action_list = []
        if self.prepare_output():
            for feature in sorted(self.feature_set):
                action_list.extend(action2real.get_real_action2s(self, feature))
        return action_list

    def __str__(self):
        ret = "spritegroup %s {\n" % (self.name)
        for spriteview in self.spriteview_list:
            ret += "\t%s\n" % str(spriteview)
        ret += "}\n"
        return ret

class SpriteView(object):
    def __init__(self, name, spriteset_list, pos):
        self.name = name
        self.spriteset_list = spriteset_list
        self.pos = pos

    def pre_process(self):
        self.spriteset_list = [x.reduce(global_constants.const_list) for x in self.spriteset_list]
        if any(map(lambda x: not isinstance(x, expression.SpriteGroupRef), self.spriteset_list)):
            raise generic.ScriptError("All items in a spritegroup must be spritegroup references", self.pos)

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite view:', self.name.value
        print (indentation+2)*' ' + 'Sprite sets:'
        for spriteset in self.spriteset_list:
            spriteset.debug_print(indentation + 4)

    def __str__(self):
        return "%s: [%s];" % (str(self.name), ", ".join([str(spriteset) for spriteset in self.spriteset_list]))

spritelayout_base_class = action2.make_sprite_group_class(False, True, True, False, True)

class SpriteLayout(spritelayout_base_class):
    def __init__(self, name, param_list, layout_sprite_list, pos = None):
        base_statement.BaseStatement.__init__(self, "spritelayout", pos, False, False)
        self.initialize(name)
        self.param_list = param_list
        if len(param_list) != 0:
            generic.print_warning("spritelayout parameters are not (yet) supported, ignoring.", pos)
        self.layout_sprite_list = layout_sprite_list

    def pre_process(self):
        for layout_sprite in self.layout_sprite_list:
            for param in layout_sprite.param_list:
                try:
                    param.value = param.value.reduce(global_constants.const_list)
                except generic.ScriptError:
                    pass
        spritelayout_base_class.pre_process(self)

    def collect_references(self):
        all_sets = []
        for layout_sprite in self.layout_sprite_list:
            all_sets.extend(layout_sprite.collect_spritesets())
        return all_sets

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite layout:', self.name.value
        print (indentation+2)*' ' + 'Parameters:'
        for param in self.param_list:
            param.debug_print(indentation + 4)
        print (indentation+2)*' ' + 'Sprites:'
        for layout_sprite in self.layout_sprite_list:
            layout_sprite.debug_print(indentation + 4)

    def __str__(self):
        return 'spritelayout %s {\n%s\n}\n' % (str(self.name), '\n'.join([str(x) for x in self.layout_sprite_list]))

    def get_action_list(self):
        action_list = []
        if self.prepare_output():
            for feature in sorted(self.feature_set):
                action_list.extend(action2layout.get_layout_action2s(self, feature))
        return action_list

class LayoutSprite(object):
    def __init__(self, ls_type, param_list, pos):
        self.type = ls_type
        self.param_list = param_list
        self.pos = pos

    # called by SpriteLayout
    def collect_spritesets(self):
        used_sets = []
        for layout_param in self.param_list:
            try:
                layout_param.value = layout_param.value.reduce(global_constants.const_list)
            except generic.ScriptError:
                pass
            if isinstance(layout_param.value, expression.SpriteGroupRef):
                used_sets.append(layout_param.value)
        return used_sets

    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite of type:', self.type
        for layout_param in self.param_list:
            layout_param.debug_print(indentation + 2)

    def __str__(self):
        return '\t%s {\n\t\t%s\n\t}' % (self.type, '\n\t\t'.join([str(layout_param) for layout_param in self.param_list]))
