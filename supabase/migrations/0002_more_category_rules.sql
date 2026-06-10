-- =============================================================================
-- Más reglas de categorización (comercios comunes en Perú) + alineación con la
-- nueva taxonomía. Idempotente: puedes correrlo varias veces sin duplicar.
-- =============================================================================

-- 1) Renombrar categoría antigua a la nueva taxonomía.
update public.category_rules set category = 'Compras personales' where category = 'Compras/tiendas';
update public.transactions   set category = 'Compras personales' where category = 'Compras/tiendas';

-- 2) Insertar reglas nuevas solo si no existen ya (por match_text).
insert into public.category_rules (match_text, category, priority)
select v.match_text, v.category, v.priority
from (values
  -- Luna (mascota)
  ('MAKRO','Luna',50),('KIVET','Luna',40),('SUPERPET','Luna',40),('PETLAND','Luna',40),
  ('MUNDO MASCOTA','Luna',40),('VETERINARIA','Luna',40),('PET ','Luna',30),
  -- Comer fuera
  ('STARBUCKS','Comer fuera',15),('JUAN VALDEZ','Comer fuera',15),('PUKU PUKU','Comer fuera',15),
  ('TANTA','Comer fuera',15),('LA LUCHA','Comer fuera',15),('BEMBOS','Comer fuera',15),
  ('KFC','Comer fuera',15),('POPEYES','Comer fuera',15),('BURGER KING','Comer fuera',15),
  ('MCDONALD','Comer fuera',15),('PARDOS','Comer fuera',15),('NORKYS','Comer fuera',15),
  ('ROKYS','Comer fuera',15),('PIZZA','Comer fuera',12),('DON BELISARIO','Comer fuera',15),
  ('SEGUNDO MUELLE','Comer fuera',15),('MADAM TUSAN','Comer fuera',15),('LA BAGUETTE','Comer fuera',15),
  ('7 SOPAS','Comer fuera',15),('LA CONDESA','Comer fuera',15),('MORELIA','Comer fuera',15),
  ('PICKADELI','Comer fuera',15),('PERU MASTER FOOD','Comer fuera',15),('SUBWAY','Comer fuera',15),
  -- Antojos
  ('HELADO DE LIMA','Antojos',15),('4D','Antojos',15),('LAREN','Antojos',15),('DUNKIN','Antojos',15),
  ('KRISPY','Antojos',15),('SAN ANTONIO','Antojos',12),('VENDOMATICA','Antojos',15),
  ('MARIA ALMENARA','Antojos',15),('DONOFRIO','Antojos',12),
  -- Delivery
  ('RAPPI','Delivery',20),('PEDIDOSYA','Delivery',20),('PEDIDOS YA','Delivery',20),
  ('UBER EATS','Delivery',22),('DIDI FOOD','Delivery',22),
  -- Transporte
  ('UBER','Transporte',18),('CABIFY','Transporte',20),('BEAT','Transporte',20),('DIDI','Transporte',18),
  ('INDRIVE','Transporte',20),('TAXI','Transporte',15),('METROPOLITANO','Transporte',20),
  -- Combustible
  ('PRIMAX','Combustible',20),('REPSOL','Combustible',20),('PETROPERU','Combustible',20),
  ('SHELL','Combustible',20),('GRIFO','Combustible',20),('ESTACION','Combustible',18),('PECSA','Combustible',20),
  -- Mercado / minimarket
  ('TOTTUS','Mercado/minimarket',10),('PLAZA VEA','Mercado/minimarket',10),('WONG','Mercado/minimarket',10),
  ('VIVANDA','Mercado/minimarket',10),('METRO','Mercado/minimarket',8),('MASS','Mercado/minimarket',10),
  ('TAMBO','Mercado/minimarket',10),('OXXO','Mercado/minimarket',10),('LISTO','Mercado/minimarket',10),
  ('FLORA Y FAUNA','Mercado/minimarket',10),('FRESH MARKET','Mercado/minimarket',10),('JOKR','Mercado/minimarket',10),
  -- Compras personales
  ('FALABELLA','Compras personales',10),('SAGA','Compras personales',10),('RIPLEY','Compras personales',10),
  ('OECHSLE','Compras personales',10),('H&M','Compras personales',10),('ZARA','Compras personales',10),
  ('FOREVER','Compras personales',10),('PLATANITOS','Compras personales',10),('RENZO COSTA','Compras personales',10),
  ('SHOPSTAR','Compras personales',10),('MERCADO LIBRE','Compras personales',10),('MERCADOLIBRE','Compras personales',10),
  ('ALIEXPRESS','Compras personales',10),('SHEIN','Compras personales',10),('AMAZON','Compras personales',8),
  -- Hogar
  ('SODIMAC','Hogar',12),('PROMART','Hogar',12),('MAESTRO','Hogar',12),('CASAIDEAS','Hogar',12),('KOMAX','Hogar',12),
  -- Deporte
  ('SMARTFIT','Deporte',20),('SMART FIT','Deporte',20),('BODYTECH','Deporte',20),('GOLD','Deporte',12),
  ('MMA STORE','Deporte',20),('MARATHON','Deporte',8),('REEBOK','Deporte',10),('NIKE','Deporte',8),('ADIDAS','Deporte',8),
  -- Servicios
  ('LUZ DEL SUR','Servicios',15),('ENEL','Servicios',15),('SEDAPAL','Servicios',15),('CALIDDA','Servicios',15),
  ('MOVISTAR','Servicios',12),('CLARO','Servicios',12),('ENTEL','Servicios',12),('BITEL','Servicios',12),
  ('WIN','Servicios',10),('DIRECTV','Servicios',12),
  -- Suscripciones
  ('NETFLIX','Suscripciones',20),('SPOTIFY','Suscripciones',20),('DISNEY','Suscripciones',20),
  ('HBO','Suscripciones',20),('MAX ','Suscripciones',15),('YOUTUBE','Suscripciones',20),('PRIME VIDEO','Suscripciones',20),
  ('AMAZON PRIME','Suscripciones',22),('APPLE.COM','Suscripciones',18),('ICLOUD','Suscripciones',20),
  ('CRUNCHYROLL','Suscripciones',20),('PARAMOUNT','Suscripciones',20),('CANVA','Suscripciones',18),
  ('CHATGPT','Suscripciones',20),('OPENAI','Suscripciones',20),('GOOGLE','Suscripciones',8),
  -- Salud
  ('INKAFARMA','Salud',15),('MIFARMA','Salud',15),('FARMACIA','Salud',12),('BOTICA','Salud',12),
  ('CLINICA','Salud',12),('AUNA','Salud',12),('SANNA','Salud',12),('OPTICA','Salud',12),('DENTAL','Salud',12),
  -- Entretenimiento
  ('CINEPLANET','Entretenimiento',12),('CINEMARK','Entretenimiento',12),('CINESTAR','Entretenimiento',12),
  ('UVK','Entretenimiento',12),('JOYLAND','Entretenimiento',12),('TEATRO','Entretenimiento',10),
  -- Educación y Desarrollo
  ('UDEMY','Educación y Desarrollo',18),('PLATZI','Educación y Desarrollo',18),('COURSERA','Educación y Desarrollo',18),
  ('CREHANA','Educación y Desarrollo',18),('DOMESTIKA','Educación y Desarrollo',18),('CRISOL','Educación y Desarrollo',12),
  ('SBS LIBRERIA','Educación y Desarrollo',15),
  -- Viajes
  ('LATAM','Viajes',18),('SKY ','Viajes',15),('JETSMART','Viajes',18),('AVIANCA','Viajes',18),
  ('BOOKING','Viajes',18),('AIRBNB','Viajes',18),('DESPEGAR','Viajes',18),('REDBUS','Viajes',18),
  ('CRUZ DEL SUR','Viajes',18),('OLTURSA','Viajes',18),('MOVIL TOURS','Viajes',18),
  -- Impuestos / Vivienda
  ('SUNAT','Impuestos',20),('SAT ','Impuestos',18),('ALQUILER','Vivienda/Casa',20),('MORA','Vivienda/Casa',15)
) as v(match_text, category, priority)
where not exists (
  select 1 from public.category_rules cr where upper(cr.match_text) = upper(v.match_text)
);
