;; ========================
;; C# 定义
;; ========================

;; 普通函数定义（局部函数）
(local_function_statement
  name: (identifier) @name
  parameters: (parameter_list) @params) @func_def

;; 方法定义（类里的方法）
(method_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @method_def

;; 构造函数定义
(constructor_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @constructor_def

;; 析构函数定义
(destructor_declaration
  name: (identifier) @name) @destructor_def

;; 类定义
(class_declaration
  name: (identifier) @name) @class_def

;; 结构体定义
(struct_declaration
  name: (identifier) @name) @struct_def

;; 接口定义
(interface_declaration
  name: (identifier) @name) @interface_def

;; 枚举定义
(enum_declaration
  name: (identifier) @name) @enum_def

;; 委托定义
(delegate_declaration
  name: (identifier) @name
  parameters: (parameter_list) @params) @delegate_def

;; 记录类型定义
(record_declaration
  name: (identifier) @name) @record_def



