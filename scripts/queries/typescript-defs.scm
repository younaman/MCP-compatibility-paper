;; ========================
;; TypeScript 定义
;; ========================

;; 普通函数定义
(function_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @func_def

;; 方法定义（类里的）
(method_definition
  name: (property_identifier) @name
  parameters: (formal_parameters) @params) @method_def

;; 类定义
(class_declaration
  name: (type_identifier) @name) @class_def

;; 接口定义
(interface_declaration
  name: (type_identifier) @name) @interface_def

;; 类型别名定义
(type_alias_declaration
  name: (type_identifier) @name) @type_def

;; 枚举定义
(enum_declaration
  name: (identifier) @name) @enum_def
