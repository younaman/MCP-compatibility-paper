;; ========================
;; Ruby 定义
;; ========================

;; 普通方法定义
(method
  name: (identifier) @name
  parameters: (method_parameters)? @params) @method_def

;; 单例方法定义（def obj.foo）
(singleton_method
  name: (identifier) @name
  parameters: (method_parameters)? @params) @singleton_def

;; 类定义
(class
  name: (constant) @classname
  body: (body_statement)?) @class_def

;; 模块定义
(module
  name: (constant) @modname
  body: (body_statement)?) @module_def
