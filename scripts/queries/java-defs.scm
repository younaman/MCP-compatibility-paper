;; ========================
;; Java 定义（方法、类、接口、枚举）
;; ========================

;; 方法定义
(method_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @method_def

;; 构造函数定义
(constructor_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @ctor_def

;; 类定义
(class_declaration
  name: (identifier) @name) @class_def

;; 接口定义
(interface_declaration
  name: (identifier) @name) @interface_def

;; 枚举定义
(enum_declaration
  name: (identifier) @name) @enum_def

;; 记录类型定义 (Java 16+)
(record_declaration
  name: (identifier) @name
  parameters: (formal_parameters) @params) @record_def
