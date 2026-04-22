;; ========================
;; Swift 定义（函数 & 方法）
;; ========================

;; 函数定义
(function_declaration
  (simple_identifier) @name) @func_def

;; 初始化函数 init
(init_declaration
  (simple_identifier) @name) @init_def

;; 类定义
(class_declaration
  (type_identifier) @name) @class_def

;; 协议定义
(protocol_declaration
  (type_identifier) @name) @protocol_def
