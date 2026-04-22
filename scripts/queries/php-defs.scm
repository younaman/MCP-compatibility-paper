;; ========================
;; PHP 定义 (Definitions)
;; ========================

;; 普通函数定义
(function_definition
  name: (name) @name
  parameters: (formal_parameters)? @params
  body: (compound_statement) @body) @func_def

;; 方法定义（类内）
(method_declaration
  name: (name) @name
  parameters: (formal_parameters)? @params
  body: (compound_statement)? @body) @method_def

;; 匿名函数定义
(anonymous_function
  parameters: (formal_parameters)? @params
  body: (compound_statement) @body) @anon_func

;; 箭头函数定义
(arrow_function
  parameters: (formal_parameters)? @params
  body: (expression) @body) @arrow_func

;; 类定义
(class_declaration
  name: (name) @classname
  body: (declaration_list) @body) @class_def

;; 接口定义
(interface_declaration
  name: (name) @iname
  body: (declaration_list) @body) @interface_def

;; trait 定义
(trait_declaration
  name: (name) @tname
  body: (declaration_list) @body) @trait_def

;; 枚举定义
(enum_declaration
  name: (name) @ename
  body: (enum_declaration_list) @body) @enum_def



