;; ========================
;; Rust 函数 & 方法调用
;; ========================

;; 方法调用：obj.method()
(call_expression
  function: (field_expression
    value: (_) @recv
    field: (field_identifier) @method)) @mcall

;; 普通函数调用：func()
(call_expression
  function: (identifier) @func) @fcall


;; ========================
;; Rust 定义
;; ========================

;; 普通函数定义
(function_item
  name: (identifier) @name
  parameters: (parameters) @params) @func_def

;; impl块中的函数定义
(impl_item
  (declaration_list
    (function_item
      name: (identifier) @name
      parameters: (parameters) @params) @impl_func_def))

;; 结构体定义
(struct_item
  name: (type_identifier) @name) @struct_def

;; 枚举定义
(enum_item
  name: (type_identifier) @name) @enum_def

;; trait定义
(trait_item
  name: (type_identifier) @name) @trait_def
