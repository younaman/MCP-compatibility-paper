;; ========================
;; PHP 调用 (Calls)
;; ========================

;; 普通函数调用 foo()
(function_call_expression
  function: (name) @func_name
  arguments: (arguments)? @args) @fcall

;; 静态调用 Class::method()
(scoped_call_expression
  scope: (_) @class
  (name) @method_name
  arguments: (arguments)? @args) @scall

;; 对象方法调用 $obj->method()
(member_call_expression
  object: (_) @recv
  (name) @method_name
  arguments: (arguments)? @args) @mcall

;; nullsafe 对象方法调用 $obj?->method()
(nullsafe_member_call_expression
  object: (_) @recv
  (name) @method_name
  arguments: (arguments)? @args) @nmcall



