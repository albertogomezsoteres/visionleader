(define (problem c-demo)
  (:domain building-indoor)

  (:objects
    robot1 - robot
    aula_c_1 aula_c_2 entrada_c escaleras_p0 escaleras_p1 escaleras_p2 - ubicacion
    planta_0 planta_1 planta_2 - planta
  )

  (:init
    (= (total-cost) 0)
    (en robot1 entrada_c)
    (abierto aula_c_1)
    (abierto aula_c_2)
    (abierto entrada_c)
    (abierto escaleras_p0)
    (abierto escaleras_p1)
    (abierto escaleras_p2)
    (en_planta aula_c_1 planta_1)
    (en_planta aula_c_2 planta_2)
    (en_planta entrada_c planta_0)
    (en_planta escaleras_p0 planta_0)
    (en_planta escaleras_p1 planta_1)
    (en_planta escaleras_p2 planta_2)
    (es_escalera escaleras_p0)
    (es_escalera escaleras_p1)
    (es_escalera escaleras_p2)
    (conectado_pasillo entrada_c escaleras_p0)
    (= (distancia entrada_c escaleras_p0) 15)
    (conectado_pasillo escaleras_p0 entrada_c)
    (= (distancia escaleras_p0 entrada_c) 15)
    (conectado_pasillo aula_c_1 escaleras_p1)
    (= (distancia aula_c_1 escaleras_p1) 15)
    (conectado_pasillo escaleras_p1 aula_c_1)
    (= (distancia escaleras_p1 aula_c_1) 15)
    (conectado_pasillo aula_c_2 escaleras_p2)
    (= (distancia aula_c_2 escaleras_p2) 15)
    (conectado_pasillo escaleras_p2 aula_c_2)
    (= (distancia escaleras_p2 aula_c_2) 15)
    (conectado_escalera_subir escaleras_p0 escaleras_p1)
    (conectado_escalera_bajar escaleras_p1 escaleras_p0)
    (conectado_escalera_subir escaleras_p1 escaleras_p2)
    (conectado_escalera_bajar escaleras_p2 escaleras_p1)
  )

  (:goal
    (en robot1 aula_c_2)
  )

  (:metric minimize (total-cost))
)
