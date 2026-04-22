;; ========================
;; Kotlin 函数/方法定义
;; ========================

;; 普通函数定义
(function_declaration
  (simple_identifier) @name
  (function_value_parameters) @params) @func_def

;; 带接收者的扩展函数定义
(function_declaration
  (receiver_type) @receiver
  (simple_identifier) @name
  (function_value_parameters) @params) @method_def

;; Lambda/匿名函数定义
(lambda_literal
  (lambda_parameters)? @params) @anon_func_def
